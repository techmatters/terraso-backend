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
        )
        filterset_class = StoryMapFilterSet
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    def resolve_configuration(self, info):
        for chapter in self.configuration["chapters"]:
            media = chapter.get("media")
            if (
                media
                and "url" in media
                and (media["type"].startswith("image") or media["type"].startswith("audio"))
            ):
                signed_url = story_map_media_upload_service.get_signed_url(media["url"])
                chapter["media"]["signedUrl"] = signed_url

        return self.configuration

    @classmethod
    def get_queryset(cls, queryset, info):
        return queryset.filter(Q(is_published=True) | Q(created_by=info.context.user))


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
