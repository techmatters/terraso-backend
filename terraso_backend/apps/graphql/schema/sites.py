# Copyright © 2021-2023 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.
from datetime import datetime

import django_filters
import graphene
from django.db import transaction
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import TypedFilter

from apps.project_management.graphql.projects import ProjectNode
from apps.project_management.models import Project, Site, sites
from apps.project_management.permission_rules import Context
from apps.project_management.permission_table import (
    ProjectAction,
    SiteAction,
    check_project_permission,
    check_site_permission,
)
from apps.soil_id.models import SoilData, SoilMetadata

from .commons import (
    BaseAuthenticatedMutation,
    BaseDeleteMutation,
    BaseMutation,
    BaseWriteMutation,
    TerrasoConnection,
)
from .constants import MutationTypes


class SiteFilter(django_filters.FilterSet):
    project = TypedFilter()
    owner = TypedFilter()
    project__member = TypedFilter(field_name="project__membership_list__memberships__user")

    class Meta:
        model = Site
        fields = ["name", "archived"]

    order_by = django_filters.OrderingFilter(
        fields=(
            ("updated_at", "updated_at"),
            ("created_at", "created_at"),
        )
    )


class SiteNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)
    seen = graphene.Boolean(required=True)
    soil_data = graphene.Field(
        "apps.soil_id.graphql.soil_data.queries.SoilDataNode",
        required=True,
        default_value=SoilData(),
    )
    soil_metadata = graphene.Field(
        "apps.soil_id.graphql.soil_metadata.queries.SoilMetadataNode",
        required=True,
        default_value=SoilMetadata(),
    )

    class Meta:
        model = Site

        fields = (
            "name",
            "latitude",
            "longitude",
            "elevation",
            "project",
            "archived",
            "owner",
            "privacy",
            "updated_at",
            "notes",
        )
        filterset_class = SiteFilter

        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        user = info.context.user
        if user.is_anonymous:
            return queryset.none()
        return sites.filter_only_sites_user_owner_or_member(user, queryset)

    @classmethod
    def privacy_enum(cls):
        return cls._meta.fields["privacy"].type.of_type()

    def resolve_seen(self, info):
        user = info.context.user
        if user.is_anonymous:
            return True
        return self.seen_by.filter(id=user.id).exists()


class SiteAddMutation(BaseWriteMutation):
    site = graphene.Field(SiteNode, required=True)

    model_class = Site

    class Input:
        name = graphene.String(required=True)
        latitude = graphene.Float(required=True)
        longitude = graphene.Float(required=True)
        elevation = graphene.Float()
        privacy = SiteNode.privacy_enum()
        project_id = graphene.ID()
        create_soil_data = graphene.Boolean()

    @classmethod
    def mutate_and_get_payload(cls, root, info, create_soil_data=True, **kwargs):
        user = info.context.user

        if not check_site_permission(user, SiteAction.CREATE, Context()):
            cls.not_allowed_create(Site)

        client_time = kwargs.pop("client_time", None)
        if not client_time:
            client_time = datetime.now()

        adding_to_project = "project_id" in kwargs
        if adding_to_project:
            project = cls.get_or_throw(Project, "project_id", kwargs["project_id"])
            if not check_project_permission(
                user, ProjectAction.ADD_NEW_SITE, Context(project=project)
            ):
                raise cls.not_allowed(MutationTypes.CREATE)
            kwargs["project"] = project
        else:
            kwargs["owner"] = info.context.user

        result = super().mutate_and_get_payload(root, info, **kwargs)
        if result.errors:
            return result

        if create_soil_data:
            SoilData.objects.create(site=result.site)
            SoilMetadata.objects.create(site=result.site)

        site = result.site
        site.mark_seen_by(user)
        metadata = {
            "latitude": site.latitude,
            "longitude": site.longitude,
            "elevation": site.elevation,
            "name": site.name,
        }
        if kwargs.get("project_id", None):
            metadata["project_id"] = kwargs["project_id"]
        return result


class SiteMarkSeenMutation(BaseAuthenticatedMutation):
    site = graphene.Field(SiteNode, required=True)

    class Input:
        id = graphene.ID(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, id):
        user = info.context.user
        site = BaseMutation.get_or_throw(Site, "id", id)
        site.mark_seen_by(user)
        return SiteMarkSeenMutation(site=site)


class SiteUpdateMutation(BaseWriteMutation):
    site = graphene.Field(SiteNode)

    model_class = Site

    class Input:
        id = graphene.ID(required=True)
        name = graphene.String()
        latitude = graphene.Float()
        longitude = graphene.Float()
        elevation = graphene.Float()
        privacy = SiteNode.privacy_enum()
        project_id = graphene.ID()

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        site = cls.get_or_throw(Site, "id", kwargs["id"])

        if not check_site_permission(user, SiteAction.UPDATE_SETTINGS, Context(site=site)):
            raise cls.not_allowed(MutationTypes.UPDATE)

        project_id = kwargs.pop("project_id", False)
        result = super().mutate_and_get_payload(root, info, **kwargs)
        if project_id is False:
            # no project id included
            return result

        # otherwise, we might need to update the site's project
        site = result.site

        # determine the potential target project
        if project_id is not None:
            project = Project.objects.get(id=project_id)
        else:
            project = None

        # check if we're allowed to make the change
        context = Context(project=project, source_site=site)
        if site.is_unaffiliated:
            if not check_project_permission(user, ProjectAction.ADD_UNAFFILIATED_SITE, context):
                raise cls.not_allowed(MutationTypes.UPDATE)
        else:
            if not check_project_permission(user, ProjectAction.TRANSFER_AFFILIATED_SITE, context):
                raise cls.not_allowed(MutationTypes.UPDATE)

        # if the check passed, make the change
        if project:
            site.add_to_project(project)
        else:
            site.add_owner(user)

        client_time = kwargs.get("client_time", None)
        if not client_time:
            client_time = datetime.now()

        metadata = {}
        for key in kwargs.keys():
            if key == "id":
                continue
            metadata[key] = getattr(site, key)
        if project_id:
            if hasattr(project, "soil_settings") and hasattr(site, "soil_data"):
                if project_id is not None:
                    metadata["project_id"] = str(project.id)

        return result


class SiteDeleteMutation(BaseDeleteMutation):
    site = graphene.Field(SiteNode, required=True)

    model_class = Site

    class Input:
        id = graphene.ID(required=True)

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        site_id = kwargs["id"]
        site = cls.get_or_throw(Site, "id", site_id)
        if not check_site_permission(user, SiteAction.DELETE, Context(site=site)):
            cls.not_allowed(MutationTypes.DELETE)

        result = super().mutate_and_get_payload(root, info, **kwargs)
        return result


class TransferredSite(graphene.ObjectType):
    old_project = graphene.Field(ProjectNode)
    site = graphene.Field(SiteNode, required=True)


class SiteTransferMutation(BaseWriteMutation):
    updated = graphene.List(graphene.NonNull(TransferredSite), required=True)
    not_found = graphene.List(graphene.NonNull(graphene.ID), required=True)
    bad_permissions = graphene.List(graphene.NonNull(SiteNode), required=True)
    project = graphene.Field(ProjectNode, required=True)

    model_class = Site

    class Input:
        site_ids = graphene.List(graphene.NonNull(graphene.ID), required=True)
        project_id = graphene.Field(graphene.ID, required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        project = cls.get_or_throw(Project, "project_id", kwargs["project_id"])

        site_ids = kwargs.get("site_ids", [])
        sites = Site.objects.filter(id__in=site_ids)
        unfound_sites = set([str(site.id) for site in sites]) - set(site_ids)

        bad_permissions = []
        to_change = []
        old_projects = []

        for site in sites:
            if site.is_unaffiliated:
                permission = check_project_permission(
                    user,
                    ProjectAction.ADD_UNAFFILIATED_SITE,
                    Context(project=project, source_site=site),
                )
            else:
                permission = check_project_permission(
                    user,
                    ProjectAction.TRANSFER_AFFILIATED_SITE,
                    Context(project=project, source_site=site),
                )

            if not permission:
                bad_permissions.append(site)
            else:
                to_change.append(site)
                old_projects.append(site.project)

        Site.bulk_change_project(to_change, project)

        return SiteTransferMutation(
            project=project,
            updated=[
                TransferredSite(site=site, old_project=project)
                for site, project in zip(to_change, old_projects)
            ],
            not_found=unfound_sites,
            bad_permissions=bad_permissions,
        )
