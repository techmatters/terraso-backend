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
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from graphene import relay
from graphene_django import DjangoObjectType

from apps.auth.services import JWTService
from apps.collaboration.graphql import CollaborationMembershipNode
from apps.collaboration.models import Membership, MembershipList
from apps.core.models import User
from apps.graphql.exceptions import (
    GraphQLNotAllowedException,
    GraphQLNotFoundException,
    GraphQLValidationException,
)
from apps.story_map.collaboration_roles import ROLE_COLLABORATOR
from apps.story_map.models.story_maps import StoryMap
from apps.story_map.notifications import send_memberships_invite_email
from apps.story_map.services import story_map_media_upload_service

from .commons import (
    BaseAuthenticatedMutation,
    BaseDeleteMutation,
    BaseUnauthenticatedMutation,
    TerrasoConnection,
)
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


class StoryMapMembershipSaveMutation(BaseAuthenticatedMutation):
    model_class = Membership
    memberships = graphene.Field(graphene.List(CollaborationMembershipNode))

    class Input:
        user_role = graphene.String()
        user_emails = graphene.List(graphene.String, required=True)
        story_map_id = graphene.String(required=True)
        story_map_slug = graphene.String(required=True)

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        if kwargs["user_role"] != ROLE_COLLABORATOR:
            logger.info(
                "Attempt to save Story Map Memberships, but user role is not collaborator",
                extra={
                    "user_role": kwargs["user_role"],
                },
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
                "Attempt to save Story Map Memberships, but story map was not found",
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
                "allowed_to_change_story_map_membership",
                user,
                {
                    "story_map": story_map,
                    "requestor_membership": user_membership,
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
                    story_map.membership_list.save_membership(
                        user_email=email,
                        user_role=kwargs["user_role"],
                        membership_status=Membership.PENDING,
                        validation_func=validate,
                    )
                ]
            ]
        except ValidationError as error:
            logger.error(
                "Attempt to save Story Map Memberships, but user is not allowed",
                extra={"error": str(error)},
            )
            raise GraphQLNotAllowedException(
                model_name=Membership.__name__, operation=MutationTypes.UPDATE
            )
        except IntegrityError as exc:
            logger.info(
                "Attempt to mutate an model, but it's not unique",
                extra={"model": Membership.__name__, "integrity_error": exc},
            )

            validation_error = ValidationError(
                message={
                    NON_FIELD_ERRORS: ValidationError(
                        message=f"This {Membership.__name__} already exists",
                        code="unique",
                    )
                },
            )
            raise GraphQLValidationException.from_validation_error(
                validation_error, model_name=Membership.__name__
            )
        except Exception as error:
            logger.error(
                "Attempt to update Story Map Memberships, but there was an error",
                extra={"error": str(error)},
            )
            raise GraphQLNotFoundException(model_name=Membership.__name__)

        pending_memberships = [
            membership["membership"] for membership in memberships if not membership["was_approved"]
        ]
        send_memberships_invite_email(user, pending_memberships, story_map)

        return cls(memberships=[membership["membership"] for membership in memberships])


class StoryMapMembershipApproveTokenMutation(BaseUnauthenticatedMutation):
    model_class = Membership
    membership = graphene.Field(CollaborationMembershipNode)
    story_map = graphene.Field(StoryMapNode)

    class Input:
        invite_token = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        request_user = info.context.user
        invite_token = kwargs["invite_token"]

        try:
            decoded_token = JWTService().verify_story_map_membership_approve_token(invite_token)
            user = User.objects.filter(pk=decoded_token["sub"]).first()
        except Exception:
            logger.exception("Failure to verify JWT token", extra={"token": invite_token})
            raise GraphQLNotAllowedException(
                model_name=StoryMap.__name__, operation=MutationTypes.UPDATE
            )

        try:
            membership = Membership.objects.get(id=decoded_token["membershipId"])
        except Exception as error:
            logger.error(
                "Attempt to approve Membership, but it was not found",
                extra={"membership_id": decoded_token["membershipId"], "error": error},
            )
            raise GraphQLNotFoundException(model_name=Membership.__name__)

        if not user and membership.pending_email is None:
            logger.error(
                "Attempt to approve a Membership, but user was not found",
                extra=kwargs,
            )
            raise GraphQLNotFoundException(model_name=User.__name__)

        story_map = membership.membership_list.story_map.get()
        if not story_map:
            logger.error(
                "Attempt to approve Membership, but Story Map was not found",
                extra={
                    "membership": membership,
                },
            )
            raise GraphQLNotFoundException(model_name=StoryMap.__name__)

        if not rules.test_rule(
            "allowed_to_approve_story_map_membership_with_token",
            request_user,
            {
                "decoded_token": decoded_token,
                "membership": membership,
            },
        ):
            logger.info(
                "Attempt to approve a Membership, but user has no permission",
                extra=kwargs,
            )
            raise GraphQLNotAllowedException(
                model_name=Membership.__name__, operation=MutationTypes.UPDATE
            )

        try:
            membership.membership_list.approve_membership(
                membership_id=membership.id,
            )
        except Exception as error:
            logger.error(
                "Attempt to approve Membership, but there was an error",
                extra={"error": str(error)},
            )
            raise GraphQLNotFoundException(model_name=Membership.__name__)

        return cls(membership=membership, story_map=story_map)


class StoryMapMembershipApproveMutation(BaseAuthenticatedMutation):
    model_class = Membership
    membership = graphene.Field(CollaborationMembershipNode)
    story_map = graphene.Field(StoryMapNode)

    class Input:
        membership_id = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        membership_id = kwargs["membership_id"]
        user = info.context.user

        if not user:
            logger.error(
                "Attempt to approve a Membership, but user was not found",
                extra=kwargs,
            )
            raise GraphQLNotFoundException(model_name=User.__name__)

        try:
            membership = Membership.objects.get(id=membership_id)
        except Exception as error:
            logger.error(
                "Attempt to approve Membership, but it was not found",
                extra={"membership_id": membership_id, "error": error},
            )
            raise GraphQLNotFoundException(model_name=Membership.__name__)

        if membership.user != user:
            logger.error(
                "Attempt to approve Membership, but user does not match",
                extra={"membership_id": membership_id, "user_id": user.pk},
            )
            raise GraphQLNotAllowedException(
                model_name=Membership.__name__, operation=MutationTypes.UPDATE
            )

        story_map = membership.membership_list.story_map.get()
        if not story_map:
            logger.error(
                "Attempt to approve Membership, but Story Map was not found",
                extra={
                    "membership": membership,
                },
            )
            raise GraphQLNotFoundException(model_name=StoryMap.__name__)

        if not rules.test_rule(
            "allowed_to_approve_story_map_membership",
            user,
            {
                "story_map": story_map,
                "membership": membership,
            },
        ):
            logger.info(
                "Attempt to approve a Membership, but user has no permission",
                extra=kwargs,
            )
            raise GraphQLNotAllowedException(
                model_name=Membership.__name__, operation=MutationTypes.UPDATE
            )

        try:
            membership.membership_list.approve_membership(
                membership_id=membership.id,
            )
        except Exception as error:
            logger.error(
                "Attempt to approve Membership, but there was an error",
                extra={"error": str(error)},
            )
            raise GraphQLNotFoundException(model_name=Membership.__name__)

        return cls(membership=membership, story_map=story_map)


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
                "Attempt to delete Story Map Memberships, but story map was not found",
                extra={"story_map_id": story_map_id, "story_map_slug": story_map_slug},
            )
            raise GraphQLNotFoundException(model_name=StoryMap.__name__)

        try:
            membership = story_map.membership_list.memberships.get(id=membership_id)
        except Membership.DoesNotExist:
            logger.error(
                "Attempt to delete Story Map Memberships, but it was not found",
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
                "Attempt to delete Story Map Memberships, but user has no permission",
                extra={"user_id": user.pk, "membership_id": membership_id},
            )
            raise GraphQLNotAllowedException(
                model_name=Membership.__name__, operation=MutationTypes.DELETE
            )

        return super().mutate_and_get_payload(root, info, **kwargs)
