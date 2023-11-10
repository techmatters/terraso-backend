# Copyright © 2023 Technology Matters
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

import graphene
import rules
from django.core.exceptions import ValidationError
from django.db import transaction
from django_filters import CharFilter, FilterSet
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField, TypedFilter

from apps.audit_logs import api as log_api
from apps.collaboration.graphql.memberships import (
    MembershipListNodeMixin,
    MembershipNodeMixin,
)
from apps.collaboration.models import Membership
from apps.core.models import User
from apps.graphql.exceptions import GraphQLValidationException
from apps.graphql.schema.commons import (
    BaseAuthenticatedMutation,
    BaseDeleteMutation,
    BaseMutation,
    BaseWriteMutation,
    TerrasoConnection,
)
from apps.graphql.schema.constants import MutationTypes
from apps.graphql.schema.users import UserNode
from apps.graphql.signals import (
    membership_added_signal,
    membership_deleted_signal,
    membership_updated_signal,
)
from apps.project_management import collaboration_roles
from apps.project_management.models import (
    Project,
    ProjectMembership,
    ProjectMembershipList,
)
from apps.project_management.models.sites import Site
from apps.soil_id.models.project_soil_settings import ProjectSoilSettings


class UserRole(graphene.Enum):
    viewer = collaboration_roles.ROLE_VIEWER
    contributor = collaboration_roles.ROLE_CONTRIBUTOR
    manager = collaboration_roles.ROLE_MANAGER


class ProjectMembershipNode(DjangoObjectType, MembershipNodeMixin):
    class Meta(MembershipNodeMixin.Meta):
        model = ProjectMembership

    user = graphene.Field(UserNode, required=True)
    user_role = graphene.Field(UserRole, required=True)

    def resolve_user_role(self, info):
        match self.user_role:
            case "viewer":
                return UserRole.viewer
            case "contributor":
                return UserRole.contributor
            case "manager":
                return UserRole.manager
            case _:
                raise Exception(f"Unexpected user role: {self.user_role}")


class ProjectMembershipFilterSet(FilterSet):
    user__email__not = CharFilter(method="filter_user_email_not")

    class Meta:
        model = ProjectMembership
        fields = {
            "user": ["exact", "in"],
            "user_role": ["exact"],
            "user__email": ["icontains", "in"],
            "membership_status": ["exact"],
        }

    def filter_user_email_not(self, queryset, name, value):
        return queryset.exclude(user__email=value)


class ProjectMembershipListNode(DjangoObjectType, MembershipListNodeMixin):
    class Meta(MembershipListNodeMixin.Meta):
        model = ProjectMembershipList

    memberships = DjangoFilterConnectionField(
        ProjectMembershipNode, filterset_class=ProjectMembershipFilterSet, required=True
    )

    def resolve_memberships(self, info, **kwargs):
        return ProjectMembershipFilterSet(kwargs).qs.filter(membership_list=self)


class ProjectFilterSet(FilterSet):
    member = TypedFilter(field_name="membership_list__memberships__user")

    class Meta:
        model = Project
        fields = {
            "name": ["exact", "icontains"],
        }


class ProjectNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)
    seen = graphene.Boolean(required=True)
    soil_settings = graphene.Field(
        "apps.soil_id.graphql.soil_data.ProjectSoilSettingsNode",
        required=True,
        default_value=ProjectSoilSettings(),
    )

    class Meta:
        model = Project

        filterset_class = ProjectFilterSet
        fields = (
            "name",
            "privacy",
            "description",
            "updated_at",
            "site_set",
            "archived",
            "membership_list",
            "measurement_units",
            "site_instructions",
        )

        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    def resolve_seen(self, info):
        user = info.context.user
        if user.is_anonymous:
            return True
        return self.seen_by.filter(id=user.id).exists()

    @classmethod
    def get_queryset(cls, queryset, info):
        # limit queries to membership lists of projects to which the user belongs
        user_pk = getattr(info.context.user, "pk", None)
        return queryset.filter(
            membership_list__memberships__user_id=user_pk,
            membership_list__memberships__deleted_at__isnull=True,
        )


class ProjectPrivacy(graphene.Enum):
    PRIVATE = Project.PRIVATE
    PUBLIC = Project.PUBLIC


class MeasurementUnits(graphene.Enum):
    METRIC = "METRIC"
    IMPERIAL = "IMPERIAL"


class ProjectAddMutation(BaseWriteMutation):
    skip_field_validation = ["membership_list", "settings"]
    project = graphene.Field(ProjectNode, required=True)

    model_class = Project

    class Input:
        name = graphene.String(required=True)
        privacy = graphene.Field(ProjectPrivacy, required=True)
        description = graphene.String()
        measurement_units = graphene.Field(MeasurementUnits, required=True)
        site_instructions = graphene.String()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        logger = cls.get_logger()
        user = info.context.user
        with transaction.atomic():
            kwargs["privacy"] = kwargs["privacy"].value
            result = super().mutate_and_get_payload(root, info, **kwargs)
            result.project.add_manager(user)

        client_time = kwargs.get("client_time", None)
        result.project.mark_seen_by(user)
        if not client_time:
            client_time = datetime.now()
        action = log_api.CREATE
        metadata = {
            "name": kwargs["name"],
            "privacy": kwargs["privacy"],
            "description": kwargs.get("description"),
        }
        logger.log(
            user=user,
            action=action,
            resource=result.project,
            client_time=client_time,
            metadata=metadata,
        )
        return result


class ProjectDeleteMutation(BaseDeleteMutation):
    project = graphene.Field(ProjectNode, required=True)

    model_class = Project

    class Input:
        id = graphene.ID(required=True)
        transfer_project_id = graphene.ID()

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        project_id = kwargs["id"]
        project = cls.get_or_throw(Project, "id", project_id)
        if not user.has_perm(Project.get_perm("delete"), project):
            cls.not_allowed()
        if "transfer_project_id" in kwargs:
            transfer_project_id = kwargs["transfer_project_id"]
            transfer_project = cls.get_or_throw(Project, "id", transfer_project_id)
            if not user.has_perm(Project.get_perm("add"), transfer_project):
                cls.not_allowed()
            project_sites = project.site_set.all()
            for site in project_sites:
                site.project = transfer_project
            Site.objects.bulk_update(project_sites, ["project"])
        result = super().mutate_and_get_payload(root, info, **kwargs)
        return result


class ProjectArchiveMutation(BaseWriteMutation):
    project = graphene.Field(ProjectNode, required=True)

    model_class = Project

    class Input:
        id = graphene.ID(required=True)
        archived = graphene.Boolean(required=True)

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        project_id = kwargs["id"]
        project = cls.get_or_throw(Project, "id", project_id)
        if not user.has_perm(Project.get_perm("archive"), project):
            cls.not_allowed()
        project_sites = project.site_set.all()
        for site in project_sites:
            site.archived = kwargs["archived"]
        Site.objects.bulk_update(project_sites, ["archived"])
        result = super().mutate_and_get_payload(root, info, **kwargs)
        return result


class ProjectUpdateMutation(BaseWriteMutation):
    project = graphene.Field(ProjectNode)

    model_class = Project

    class Input:
        id = graphene.ID(required=True)
        name = graphene.String()
        privacy = graphene.Field(ProjectPrivacy)
        description = graphene.String()
        measurement_units = graphene.Field(MeasurementUnits)
        site_instructions = graphene.String()

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        logger = cls.get_logger()
        user = info.context.user
        project_id = kwargs["id"]
        project = cls.get_or_throw(Project, "id", project_id)
        cls.remove_null_fields(kwargs, ["privacy", "measurement_units"])
        if not user.has_perm(Project.get_perm("change"), project):
            cls.not_allowed()

        metadata = {
            "name": kwargs.get("name"),
            "description": kwargs["description"] if "description" in kwargs else None,
        }

        if privacy := kwargs.get("privacy"):
            metadata["privacy"] = privacy.value

        logger.log(
            user=user,
            action=log_api.CHANGE,
            resource=project,
            client_time=datetime.now(),
            metadata=metadata,
        )

        return super().mutate_and_get_payload(root, info, **kwargs)


class ProjectAddUserMutation(BaseWriteMutation):
    project = graphene.Field(ProjectNode, required=True)
    membership = graphene.Field(ProjectMembershipNode, required=True)

    model_class = ProjectMembership

    class Input:
        project_id = graphene.ID(required=True)
        user_id = graphene.ID(required=True)
        role = graphene.Field(UserRole, required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, project_id, user_id, role):
        if role not in Project.ROLES:
            raise GraphQLValidationException(message=f"Invalid role: {role}")
        project = cls.get_or_throw(Project, "project_id", project_id)
        user = cls.get_or_throw(User, "user_id", user_id)
        request_user = info.context.user
        requester_membership = project.get_membership(request_user)
        if not requester_membership:
            cls.not_allowed_create(model=Membership, msg="User does not belong to project")

        def validate(context):
            if not rules.test_rule(
                "allowed_to_add_member_to_project",
                request_user,
                {"project": project, "requester_membership": requester_membership},
            ):
                raise ValidationError("User cannot add membership to this project")

        if membership := project.get_membership(user):
            # if user is already a member, don't do anything
            return ProjectAddUserMutation(project=project, membership=membership)

        # add membership
        try:
            _, membership = project.membership_list.save_membership(
                user_email=user.email,
                user_role=role.value,
                membership_status=Membership.APPROVED,
                validation_func=validate,
                membership_class=ProjectMembership,
            )
        except ValidationError as e:
            cls.not_allowed_create(model=cls.model_class, msg=e.message)

        membership_added_signal.send(sender=cls, membership=membership, user=request_user)

        return ProjectAddUserMutation(project=project, membership=membership)


class ProjectDeleteUserMutation(BaseWriteMutation):
    project = graphene.Field(ProjectNode, required=True)
    membership = graphene.Field(ProjectMembershipNode, required=True)

    model_class = Membership

    class Input:
        project_id = graphene.ID(required=True)
        user_id = graphene.ID(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, project_id, user_id):
        # check if user has proper permissions
        project = cls.get_or_throw(Project, "project_id", project_id)
        user = cls.get_or_throw(User, "user_id", user_id)
        requester = info.context.user
        requester_membership = project.get_membership(requester)
        if not requester_membership:
            cls.not_allowed(
                MutationTypes.DELETE,
                msg="User cannot delete other users" " from project where they are not a member",
            )
        target_membership = project.get_membership(user)
        if not target_membership:
            cls.not_allowed(
                MutationTypes.DELETE, msg="Cannot delete a user membership that does not exist"
            )
        if not rules.test_rule(
            "allowed_to_delete_user_from_project",
            requester,
            {
                "project": project,
                "requester_membership": requester_membership,
                "target_membership": target_membership,
            },
        ):
            cls.not_allowed(
                MutationTypes.DELETE, msg="User not allowed to remove member from project"
            )
        # remove membership
        membership = project.get_membership(user)
        membership.delete()

        membership_deleted_signal.send(sender=cls, membership=target_membership, user=requester)

        return ProjectDeleteUserMutation(project=project, membership=membership)


class ProjectUpdateUserRoleMutation(BaseWriteMutation):
    model_class = ProjectMembership

    project = graphene.Field(ProjectNode, required=True)
    membership = graphene.Field(ProjectMembershipNode, required=True)

    class Input:
        project_id = graphene.ID(required=True)
        user_id = graphene.ID(required=True)
        new_role = graphene.Field(UserRole, required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, project_id, user_id, new_role):
        project = cls.get_or_throw(Project, "project_id", project_id)
        requester = info.context.user

        if not (requester_membership := project.get_membership(requester)):
            cls.not_allowed(MutationTypes.UPDATE, msg="Requesting member not a member of project")

        target_user = cls.get_or_throw(User, "user_id", user_id)
        if not (target_membership := project.get_membership(target_user)):
            cls.not_allowed(MutationTypes.UPDATE, msg="Target user not a member of project")

        if not rules.test_rule(
            "allowed_to_change_user_project_role",
            requester,
            {
                "project": project,
                "requester_membership": requester_membership,
                "target_membership": target_membership,
                "user_role": new_role,
            },
        ):
            cls.not_allowed(
                MutationTypes.UPDATE, msg="User is not allowed to change other user role"
            )

        target_membership.user_role = new_role.value
        target_membership.save()

        membership_updated_signal.send(sender=cls, membership=target_membership, user=requester)

        return ProjectUpdateUserRoleMutation(project=project, membership=target_membership)


class ProjectMarkSeenMutation(BaseAuthenticatedMutation):
    project = graphene.Field(ProjectNode, required=True)

    class Input:
        id = graphene.ID(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, id):
        user = info.context.user
        project = BaseMutation.get_or_throw(Project, "id", id)
        project.mark_seen_by(user)
        return ProjectMarkSeenMutation(project=project)
