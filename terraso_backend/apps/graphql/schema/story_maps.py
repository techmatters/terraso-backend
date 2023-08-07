﻿# Copyright © 2023 Technology Matters
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

import django_filters
import graphene
import structlog
from django.db import transaction
from django.db.models import Q
from graphene import relay
from graphene_django import DjangoObjectType

from apps.collaboration.graphql import CollaborationMembershipNode
from apps.collaboration.models import Membership
from apps.graphql.exceptions import GraphQLNotAllowedException, GraphQLNotFoundException
from apps.story_map.collaboration_roles import ROLE_CONTRIBUTOR
from apps.story_map.models.story_maps import StoryMap
from apps.story_map.services import story_map_media_upload_service

from .commons import BaseAuthenticatedMutation, BaseDeleteMutation, TerrasoConnection
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class StoryMapFilterSet(django_filters.FilterSet):
    created_by__email__not = django_filters.CharFilter(method="filter_created_by_email_not")

    class Meta:
        model = StoryMap
        fields = {
            "slug": ["exact"],
            "story_map_id": ["exact"],
            "created_by__email": ["exact"],
        }

    def filter_created_by_email_not(self, queryset, name, value):
        return queryset.exclude(created_by__email=value)


class StoryMapNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = StoryMap
        fields = (
            "id",
            "slug",
            "story_map_id",
            "title",
            "configuration",
            "is_published",
            "created_by",
            "created_at",
            "updated_at",
            "published_at",
            "membership_list",
        )
        filterset_class = StoryMapFilterSet
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    def resolve_configuration(self, info):
        for chapter in self.configuration["chapters"]:
            media = chapter.get("media")
            if media and "url" in media and media["type"].startswith(("image", "audio", "video")):
                signed_url = story_map_media_upload_service.get_signed_url(media["url"])
                chapter["media"]["signedUrl"] = signed_url

        return self.configuration

    @classmethod
    def get_queryset(cls, queryset, info):
        user_pk = getattr(info.context.user, "pk", False)
        return queryset.filter(
            Q(is_published=True)
            | Q(created_by=user_pk)
            | Q(
                membership_list__memberships__user=user_pk,
                membership_list__memberships__membership_status=Membership.APPROVED,
            )
        )


class StoryMapDeleteMutation(BaseDeleteMutation):
    story_map = graphene.Field(StoryMapNode)

    model_class = StoryMap

    class Input:
        id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        story_map = StoryMap.objects.get(pk=kwargs["id"])

        if not user.has_perm(StoryMap.get_perm("delete"), obj=story_map):
            logger.info(
                "Attempt to delete a StoryMap, but user lacks permission",
                extra={"user_id": user.pk, "story_map_id": str(story_map.id)},
            )
            raise GraphQLNotAllowedException(
                model_name=StoryMap.__name__, operation=MutationTypes.DELETE
            )
        return super().mutate_and_get_payload(root, info, **kwargs)


class StoryMapMembershipSaveMutation(BaseAuthenticatedMutation):
    model_class = Membership
    memberships = graphene.Field(graphene.List(CollaborationMembershipNode))

    class Input:
        user_role = graphene.String()
        membership_status = graphene.String()
        user_emails = graphene.List(graphene.String, required=True)
        story_map_id = graphene.String(required=True)
        story_map_slug = graphene.String(required=True)

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        if kwargs["user_role"] != ROLE_CONTRIBUTOR:
            logger.info(
                "Attempt to save a Membership, but user has no permission",
                extra=kwargs,
            )
            raise GraphQLNotAllowedException(
                model_name=Membership.__name__, operation=MutationTypes.UPDATE
            )

        story_map_id = kwargs["story_map_id"]
        story_map_slug = kwargs["story_map_slug"]

        try:
            story_map = StoryMap.objects.get(slug=story_map_slug, story_map_id=story_map_id)
        except Exception as error:
            logger.error(
                "Attempt to save a Membership, but Story Map was not found",
                extra={
                    "story_map_id": story_map_id,
                    "story_map_slug": story_map_slug,
                    "error": error,
                },
            )
            raise GraphQLNotFoundException(model_name=StoryMap.__name__)

        if not user.has_perm(
            StoryMap.get_perm("save_membership"),
            obj={
                "story_map": story_map,
                "membership": kwargs,
            },
        ):
            logger.info(
                "Attempt to update a Membership, but user has no permission",
                extra=kwargs,
            )
            raise GraphQLNotAllowedException(
                model_name=Membership.__name__, operation=MutationTypes.UPDATE
            )

        try:
            memberships = [
                story_map.membership_list.save_member(
                    {
                        "user_email": email,
                        "user_role": kwargs["user_role"],
                    }
                )
                for email in kwargs["user_emails"]
            ]
        except Exception as error:
            logger.error(
                "Attempt to update Story Map Memberships, but there was an error",
                extra={"error": str(error)},
            )
            raise GraphQLNotFoundException(model_name=Membership.__name__)

        return cls(memberships=memberships)


class StoryMapMembershipDeleteMutation(BaseDeleteMutation):
    membership = graphene.Field(CollaborationMembershipNode)

    model_class = Membership

    class Input:
        id = graphene.ID()
        story_map_id = graphene.String(required=True)
        story_map_slug = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        membership_id = kwargs["id"]
        story_map_id = kwargs["story_map_id"]
        story_map_slug = kwargs["story_map_slug"]

        try:
            story_map = StoryMap.objects.get(slug=story_map_slug, story_map_id=story_map_id)
        except StoryMap.DoesNotExist:
            logger.error(
                "Attempt to save a Membership, but Story Map was not found",
                extra={"story_map_id": story_map_id, "story_map_slug": story_map_slug},
            )
            raise GraphQLNotFoundException(model_name=StoryMap.__name__)

        try:
            membership = story_map.membership_list.memberships.get(id=membership_id)
        except Membership.DoesNotExist:
            logger.error(
                "Attempt to delete a Membership, but it was not found",
                extra={"membership_id": membership_id},
            )
            raise GraphQLNotFoundException(model_name=Membership.__name__)

        if not user.has_perm(
            StoryMap.get_perm("delete_membership"),
            obj={
                "story_map": story_map,
                "membership": membership,
            },
        ):
            logger.info(
                "Attempt to delete a Membership, but user has no permission",
                extra={"user_id": user.pk, "membership_id": membership_id},
            )
            raise GraphQLNotAllowedException(
                model_name=Membership.__name__, operation=MutationTypes.DELETE
            )

        return super().mutate_and_get_payload(root, info, **kwargs)
