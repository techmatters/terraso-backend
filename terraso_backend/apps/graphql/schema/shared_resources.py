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

import graphene
import rules
import structlog
from django.conf import settings
from django.db.models import Q, Subquery
from graphene import relay
from graphene_django import DjangoObjectType

from apps.collaboration.models import Membership as CollaborationMembership
from apps.core.models import Group, Landscape, SharedResource
from apps.graphql.exceptions import GraphQLNotAllowedException, GraphQLNotFoundException

from . import GroupNode, LandscapeNode
from .commons import BaseWriteMutation, TerrasoConnection
from .constants import MutationTypes
from .data_entries import DataEntryNode
from .visualization_config import VisualizationConfigNode

logger = structlog.get_logger(__name__)


class SourceNode(graphene.Union):
    class Meta:
        types = (VisualizationConfigNode, DataEntryNode)


class TargetNode(graphene.Union):
    class Meta:
        types = (GroupNode, LandscapeNode)


class SharedResourceNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)
    source = graphene.Field(SourceNode)
    target = graphene.Field(TargetNode)
    download_url = graphene.String()
    share_url = graphene.String()

    class Meta:
        model = SharedResource
        fields = ["id", "share_access", "share_uuid"]
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    def resolve_source(self, info, **kwargs):
        return self.source

    def resolve_target(self, info, **kwargs):
        return self.target

    def resolve_download_url(self, info, **kwargs):
        return f"{settings.API_ENDPOINT}/shared-data/download/{self.share_uuid}"

    def resolve_share_url(self, info, **kwargs):
        target = self.target
        entity = (
            "groups"
            if isinstance(target, Group)
            else "landscapes"
            if isinstance(target, Landscape)
            else None
        )
        if not entity:
            return None
        slug = target.slug
        share_uuid = self.share_uuid
        return f"{settings.WEB_CLIENT_URL}/{entity}/{slug}/download/{share_uuid}"


class SharedResourceRelayNode:
    @classmethod
    def Field(cls):
        return graphene.Field(SharedResourceNode, share_uuid=graphene.String(required=True))


def resolve_shared_resource(root, info, share_uuid=None):
    if not share_uuid:
        return None

    user_pk = getattr(info.context.user, "pk", False)
    user_groups_ids = Subquery(
        Group.objects.filter(
            membership_list__memberships__deleted_at__isnull=True,
            membership_list__memberships__user__id=user_pk,
            membership_list__memberships__membership_status=CollaborationMembership.APPROVED,
        ).values("id")
    )
    user_landscape_ids = Subquery(
        Landscape.objects.filter(
            membership_list__memberships__deleted_at__isnull=True,
            membership_list__memberships__user__id=user_pk,
            membership_list__memberships__membership_status=CollaborationMembership.APPROVED,
        ).values("id")
    )

    share_access_all = Q(share_access=SharedResource.SHARE_ACCESS_ALL)
    share_access_members = Q(
        Q(share_access=SharedResource.SHARE_ACCESS_TARGET_MEMBERS)
        & Q(Q(target_object_id__in=user_groups_ids) | Q(target_object_id__in=user_landscape_ids))
    )

    return SharedResource.objects.filter(
        Q(share_uuid=share_uuid) & Q(share_access_all | share_access_members)
    ).first()


class SharedResourceUpdateMutation(BaseWriteMutation):
    shared_resource = graphene.Field(SharedResourceNode)

    model_class = SharedResource

    class Input:
        id = graphene.ID(required=True)
        share_access = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        try:
            shared_resource = SharedResource.objects.get(pk=kwargs["id"])
        except SharedResource.DoesNotExist:
            logger.error(
                "SharedResource not found",
                extra={"shared_resource_id": kwargs["id"]},
            )
            raise GraphQLNotFoundException(field="id", model_name=SharedResource.__name__)

        if not rules.test_rule("allowed_to_change_shared_resource", user, shared_resource):
            logger.info(
                "Attempt to update a SharedResource, but user lacks permission",
                extra={"user_id": user.pk, "shared_resource_id": str(shared_resource.pk)},
            )
            raise GraphQLNotAllowedException(
                model_name=SharedResource.__name__, operation=MutationTypes.UPDATE
            )
        kwargs["share_access"] = SharedResource.get_share_access_from_text(kwargs["share_access"])
        return super().mutate_and_get_payload(root, info, **kwargs)
