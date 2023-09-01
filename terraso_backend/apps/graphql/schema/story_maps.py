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
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from graphene import relay
from graphene_django import DjangoObjectType

from apps.collaboration.graphql import CollaborationMembershipNode
from apps.collaboration.models import Membership, MembershipList
from apps.graphql.exceptions import GraphQLNotAllowedException, GraphQLNotFoundException
from apps.story_map.collaboration_roles import ROLE_COLLABORATOR
from apps.story_map.models.story_maps import StoryMap
from apps.story_map.notifications import send_memberships_invite_email
from apps.story_map.services import story_map_media_upload_service

from .commons import BaseAuthenticatedMutation, BaseDeleteMutation, TerrasoConnection
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class StoryMapFilterSet(django_filters.FilterSet):
    can_change__email__not = django_filters.CharFilter(method="filter_can_change_by_email_not")
    can_change__email = django_filters.CharFilter(method="filter_can_change_by_email")

    class Meta:
        model = StoryMap
        fields = {
            "slug": ["exact"],
            "story_map_id": ["exact"],
        }

    def filter_can_change_by_email(self, queryset, name, value):
        approved_memberships = Membership.objects.filter(
            user__email=value,
            membership_status=Membership.APPROVED,
            membership_list=OuterRef("membership_list"),
        )
        return queryset.filter(Q(created_by__email=value) | Exists(approved_memberships))

    def filter_can_change_by_email_not(self, queryset, name, value):
        return queryset.exclude(
            Q(created_by__email=value) | Q(membership_list__memberships__user__email=value)
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

        if self.created_by == user:
            return self.membership_list

        if self.membership_list.is_member(user):
            return self.membership_list
        return None

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
        ).distinct()


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

        if kwargs["user_role"] != ROLE_COLLABORATOR:
            logger.info(
                "Attempt to save a membership, but user has no permission",
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
                "Attempt to save a membership, but story map was not found",
                extra={
                    "story_map_id": story_map_id,
                    "story_map_slug": story_map_slug,
                    "error": error,
                },
            )
            raise GraphQLNotFoundException(model_name=StoryMap.__name__)

        if not story_map.membership_list:
            story_map.membership_list = MembershipList.objects.create(
                enroll_method=MembershipList.ENROLL_METHOD_INVITE,
                membership_type=MembershipList.MEMBERSHIP_TYPE_CLOSED,
            )
            story_map.save()

        user_membership = story_map.membership_list.memberships.filter(user=user).first()

        def validate(context):
            if not rules.test_rule(
                "allowed_to_save_story_map_membership",
                user,
                {
                    "story_map": story_map,
                    "user_membership": user_membership,
                    **context,
                },
            ):
                raise ValidationError("User cannot request membership")

        try:
            memberships = [
                {
                    "membership": result[1],
                    "was_approved": result[0],
                }
                for email in kwargs["user_emails"]
                for result in [
                    story_map.membership_list.save_member(
                        user_email=email,
                        user_role=kwargs["user_role"],
                        membership_status=Membership.APPROVED,
                        validation_func=validate,
                    )
                ]
            ]
        except ValidationError as error:
            logger.error(
                "Attempt to save a Membership, but user is not allowed",
                extra={"error": str(error)},
            )
            raise GraphQLNotAllowedException(
                model_name=Membership.__name__, operation=MutationTypes.UPDATE
            )
        except Exception as error:
            logger.error(
                "Attempt to update Story Map Memberships, but there was an error",
                extra={"error": str(error)},
            )
            raise GraphQLNotFoundException(model_name=Membership.__name__)

        approved_memberships = [
            membership["membership"] for membership in memberships if membership["was_approved"]
        ]
        send_memberships_invite_email(approved_memberships, story_map)

        return cls(memberships=[membership["membership"] for membership in memberships])


class StoryMapMembershipDeleteMutation(BaseDeleteMutation):
    membership = graphene.Field(CollaborationMembershipNode)

    model_class = Membership

    class Input:
        id = graphene.ID()
        story_map_id = graphene.String(required=True)
        story_map_slug = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        # TODO check delete permissions for members
        user = info.context.user
        membership_id = kwargs["id"]
        story_map_id = kwargs["story_map_id"]
        story_map_slug = kwargs["story_map_slug"]

        try:
            story_map = StoryMap.objects.get(slug=story_map_slug, story_map_id=story_map_id)
        except StoryMap.DoesNotExist:
            logger.error(
                "Attempt to save a membership, but story map was not found",
                extra={"story_map_id": story_map_id, "story_map_slug": story_map_slug},
            )
            raise GraphQLNotFoundException(model_name=StoryMap.__name__)

        try:
            membership = story_map.membership_list.memberships.get(id=membership_id)
        except Membership.DoesNotExist:
            logger.error(
                "Attempt to delete a membership, but it was not found",
                extra={"membership_id": membership_id},
            )
            raise GraphQLNotFoundException(model_name=Membership.__name__)

        if not rules.test_rule(
            "allowed_to_delete_story_map_membership",
            user,
            {
                "story_map": story_map,
                "membership": membership,
            },
        ):
            logger.info(
                "Attempt to delete a membership, but user has no permission",
                extra={"user_id": user.pk, "membership_id": membership_id},
            )
            raise GraphQLNotAllowedException(
                model_name=Membership.__name__, operation=MutationTypes.DELETE
            )

        return super().mutate_and_get_payload(root, info, **kwargs)
