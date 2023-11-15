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

import django_filters
import graphene
import rules
import structlog
from django.db.models import Q
from graphene import relay
from graphene_django import DjangoObjectType

from apps.graphql.exceptions import GraphQLNotAllowedException
from apps.story_map.models.story_maps import StoryMap
from apps.story_map.services import story_map_media_upload_service

from .commons import BaseDeleteMutation, TerrasoConnection
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class StoryMapFilterSet(django_filters.FilterSet):
    memberships__user__email__not = django_filters.CharFilter(
        method="filter_memberships_user_email_not"
    )
    memberships__user__email = django_filters.CharFilter(method="filter_memberships_user_email")

    class Meta:
        model = StoryMap
        fields = {
            "slug": ["exact"],
            "story_map_id": ["exact"],
        }

    def filter_memberships_user_email_not(self, queryset, name, value):
        return queryset.exclude(
            Q(
                membership_list__memberships__user__email=value,
                membership_list__memberships__deleted_at__isnull=True,
            )
            | Q(created_by__email=value)
        )

    def filter_memberships_user_email(self, queryset, name, value):
        return queryset.filter(
            Q(
                membership_list__memberships__user__email=value,
                membership_list__memberships__deleted_at__isnull=True,
            )
            | Q(created_by__email=value)
        )


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
        is_owner = self.created_by == info.context.user
        is_approved_member = self.membership_list and self.membership_list.is_approved_member(
            info.context.user
        )

        if not self.is_published and not is_owner and not is_approved_member:
            return None

        for chapter in self.configuration["chapters"]:
            media = chapter.get("media")
            if media and "url" in media and media["type"].startswith(("image", "audio", "video")):
                signed_url = story_map_media_upload_service.get_signed_url(media["url"])
                chapter["media"]["signedUrl"] = signed_url

        return self.configuration

    def resolve_membership_list(self, info):
        user = info.context.user
        if user.is_anonymous or self.membership_list is None:
            return None

        is_owner = self.created_by == info.context.user
        is_member = self.membership_list and self.membership_list.is_member(info.context.user)

        if is_owner or is_member:
            return self.membership_list

        return None

    @classmethod
    def get_queryset(cls, queryset, info):
        user_pk = getattr(info.context.user, "pk", False)

        base_query = Q(is_published=True) | Q(created_by=user_pk)
        membership_query = (
            Q(membership_list__memberships__user=user_pk) if user_pk is not None else Q()
        )

        final_query = base_query | membership_query

        return queryset.filter(final_query).distinct()


class StoryMapDeleteMutation(BaseDeleteMutation):
    story_map = graphene.Field(StoryMapNode)

    model_class = StoryMap

    class Input:
        id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        story_map = StoryMap.objects.get(pk=kwargs["id"])

        if not rules.test_rule("allowed_to_delete_story_map", user, story_map):
            logger.info(
                "Attempt to delete a StoryMap, but user lacks permission",
                extra={"user_id": user.pk, "story_map_id": str(story_map.id)},
            )
            raise GraphQLNotAllowedException(
                model_name=StoryMap.__name__, operation=MutationTypes.DELETE
            )

        return super().mutate_and_get_payload(root, info, **kwargs)
