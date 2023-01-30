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

import graphene
import structlog
from django.db.models import Q
from graphene import relay
from graphene_django import DjangoObjectType

from apps.graphql.exceptions import GraphQLNotAllowedException
from apps.story_map.models.story_maps import StoryMap

from .commons import BaseDeleteMutation, BaseWriteMutation, TerrasoConnection
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class StoryMapNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = StoryMap
        filter_fields = {
            "slug": ["exact", "icontains"],
        }
        fields = (
            "id",
            "slug",
            "title",
            "configuration",
            "is_published",
            "created_by",
            "created_at",
        )
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        return queryset.filter(Q(is_published=True) | Q(created_by=info.context.user))


class StoryMapAddMutation(BaseWriteMutation):
    story_map = graphene.Field(StoryMapNode)

    model_class = StoryMap

    class Input:
        title = graphene.String(required=True)
        configuration = graphene.JSONString(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        if not cls.is_update(kwargs):
            kwargs["created_by"] = user

        return super().mutate_and_get_payload(root, info, **kwargs)


class StoryMapUpdateMutation(BaseWriteMutation):
    story_map = graphene.Field(StoryMapNode)

    model_class = StoryMap

    class Input:
        id = graphene.ID(required=True)
        title = graphene.String()
        configuration = graphene.JSONString()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        story_map = StoryMap.objects.get(pk=kwargs["id"])

        if not user.has_perm(StoryMap.get_perm("change"), obj=story_map):
            logger.info(
                "Attempt to update a StoryMap, but user lacks permission",
                extra={"user_id": user.pk, "story_map_id": str(story_map.id)},
            )
            raise GraphQLNotAllowedException(
                model_name=StoryMap.__name__, operation=MutationTypes.UPDATE
            )

        return super().mutate_and_get_payload(root, info, **kwargs)


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
