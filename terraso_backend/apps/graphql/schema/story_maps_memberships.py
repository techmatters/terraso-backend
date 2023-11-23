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
import structlog
from django.db import transaction

from apps.auth.services import JWTService
from apps.collaboration.graphql import (
    BaseMembershipSaveMutation,
    CollaborationMembershipNode,
)
from apps.collaboration.models import Membership, MembershipList
from apps.core.models import User
from apps.graphql.exceptions import GraphQLNotAllowedException, GraphQLNotFoundException
from apps.graphql.schema.story_maps import StoryMapNode
from apps.story_map.collaboration_roles import ROLE_EDITOR
from apps.story_map.models.story_maps import StoryMap
from apps.story_map.notifications import send_memberships_invite_email

from .commons import BaseAuthenticatedMutation, BaseDeleteMutation
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class StoryMapMembershipSaveMutation(BaseMembershipSaveMutation):
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

        cls.validate_role(kwargs["user_role"], [ROLE_EDITOR])

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

        memberships = cls.save_memberships(
            user=user,
            validation_rule="allowed_to_change_story_map_membership",
            validation_context={
                "story_map": story_map,
                "requestor_membership": user_membership,
            },
            membership_list=story_map.membership_list,
            kwargs={
                **kwargs,
                "membership_status": Membership.PENDING,
            },
        )

        pending_memberships = [
            membership["membership"]
            for membership in memberships
            if not membership["context"]["is_membership_approved"]
        ]
        send_memberships_invite_email(user, pending_memberships, story_map)

        return cls(memberships=[membership["membership"] for membership in memberships])


class StoryMapMembershipApproveTokenMutation(BaseAuthenticatedMutation):
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
                "Attempt to approve Story Map Membership, but it was not found",
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
            error = GraphQLNotAllowedException(
                model_name=Membership.__name__,
                operation=MutationTypes.UPDATE,
                message="permissions_validation",
            )
            return cls(
                errors=[{"message": str(error)}],
                story_map=StoryMap(
                    id="",
                    title=story_map.title,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                ),
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
