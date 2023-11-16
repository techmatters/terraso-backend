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

from apps.collaboration.graphql import (
    BaseMembershipSaveMutation,
    CollaborationMembershipNode,
)
from apps.collaboration.models import Membership as CollaborationMembership
from apps.collaboration.models import MembershipList
from apps.core import group_collaboration_roles
from apps.core.models import Group
from apps.graphql.exceptions import GraphQLNotAllowedException, GraphQLNotFoundException
from apps.graphql.schema.groups import GroupNode
from apps.notifications.email import EmailNotification

from .commons import BaseDeleteMutation
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class GroupMembershipSaveMutation(BaseMembershipSaveMutation):
    model_class = CollaborationMembership
    memberships = graphene.Field(graphene.List(CollaborationMembershipNode))
    group = graphene.Field(GroupNode)

    class Input:
        user_role = graphene.String()
        user_emails = graphene.List(graphene.String, required=True)
        group_slug = graphene.String(required=True)
        membership_status = graphene.String()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        user_role = (
            kwargs["user_role"] if "user_role" in kwargs else group_collaboration_roles.ROLE_MEMBER
        )

        cls.validate_role(user_role, group_collaboration_roles.ALL_ROLES)

        group_slug = kwargs["group_slug"]

        try:
            group = Group.objects.get(slug=group_slug)
        except Exception as error:
            logger.error(
                "Attempt to save Story Map Memberships, but story map was not found",
                extra={
                    "group_slug": group_slug,
                    "error": error,
                },
            )
            raise GraphQLNotFoundException(model_name=Group.__name__)

        is_closed_group = (
            group.membership_list.membership_type == MembershipList.MEMBERSHIP_TYPE_CLOSED
        )

        membership_status = (
            CollaborationMembership.APPROVED
            if not is_closed_group
            else kwargs["membership_status"]
            if "membership_status" in kwargs
            else CollaborationMembership.PENDING
        )

        memberships_save_result = cls.save_memberships(
            user=user,
            validation_rule="allowed_to_change_group_membership",
            validation_context={"group": group},
            membership_list=group.membership_list,
            kwargs={
                **kwargs,
                "user_role": user_role,
                "membership_status": membership_status,
            },
        )

        if group.membership_list.membership_type == MembershipList.MEMBERSHIP_TYPE_CLOSED:
            for membership_result in memberships_save_result:
                context = membership_result["context"]
                membership = membership_result["membership"]
                if context["is_new"]:
                    EmailNotification.send_membership_request(membership.user, group)
                if context["is_membership_approved"]:
                    EmailNotification.send_membership_approval(membership.user, group)

        return cls(
            memberships=[
                membership_result["membership"] for membership_result in memberships_save_result
            ],
            group=group,
        )


class GroupMembershipDeleteMutation(BaseDeleteMutation):
    membership = graphene.Field(CollaborationMembershipNode)
    group = graphene.Field(GroupNode)

    model_class = CollaborationMembership

    class Input:
        id = graphene.ID(required=True)
        group_slug = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        membership_id = kwargs["id"]
        group_slug = kwargs["group_slug"]

        try:
            group = Group.objects.get(slug=group_slug)
        except Group.DoesNotExist:
            logger.error(
                "Attempt to delete Group Membership, but group was not found",
                extra={"group_slug": group_slug},
            )
            raise GraphQLNotFoundException(model_name=Group.__name__)

        try:
            membership = group.membership_list.memberships.get(id=membership_id)
        except CollaborationMembership.DoesNotExist:
            logger.error(
                "Attempt to delete Group Membership, but membership was not found",
                extra={"membership_id": membership_id},
            )
            raise GraphQLNotFoundException(model_name=CollaborationMembership.__name__)

        if not rules.test_rule(
            "allowed_to_delete_group_membership",
            user,
            {
                "group": group,
                "membership": membership,
            },
        ):
            logger.info(
                "Attempt to delete Group Memberships, but user lacks permission",
                extra={"user_id": user.pk, "membership_id": membership_id},
            )
            raise GraphQLNotAllowedException(
                model_name=CollaborationMembership.__name__, operation=MutationTypes.DELETE
            )

        if not rules.test_rule(
            "allowed_group_managers_count",
            user,
            {
                "group": group,
                "membership": membership,
            },
        ):
            logger.info(
                "Attempt to update a Membership, but cannot remove last manager",
                extra={"user_id": user.pk, "membership_id": membership_id},
            )
            raise GraphQLNotAllowedException(
                model_name=CollaborationMembership.__name__,
                operation=MutationTypes.DELETE,
                message="manager_count",
            )

        result = super().mutate_and_get_payload(root, info, **kwargs)
        return cls(membership=result.membership, group=group)
