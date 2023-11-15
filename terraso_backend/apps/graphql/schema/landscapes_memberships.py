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
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError, transaction

from apps.collaboration.graphql import CollaborationMembershipNode
from apps.collaboration.models import Membership as CollaborationMembership
from apps.core import landscape_collaboration_roles
from apps.core.models import Landscape
from apps.graphql.exceptions import (
    GraphQLNotAllowedException,
    GraphQLNotFoundException,
    GraphQLValidationException,
)
from apps.graphql.schema.landscapes import LandscapeNode

from .commons import BaseAuthenticatedMutation, BaseDeleteMutation
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class LandscapeMembershipSaveMutation(BaseAuthenticatedMutation):
    model_class = CollaborationMembership
    memberships = graphene.Field(graphene.List(CollaborationMembershipNode))
    landscape = graphene.Field(LandscapeNode)

    class Input:
        user_role = graphene.String(required=True)
        user_emails = graphene.List(graphene.String, required=True)
        landscape_slug = graphene.String(required=True)

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        if kwargs["user_role"] not in landscape_collaboration_roles.ALL_ROLES:
            logger.info(
                "Attempt to save Landscape Memberships, but user role is not valid",
                extra={
                    "user_role": kwargs["user_role"],
                },
            )
            raise GraphQLNotAllowedException(
                model_name=CollaborationMembership.__name__, operation=MutationTypes.UPDATE
            )

        landscape_slug = kwargs["landscape_slug"]

        try:
            landscape = Landscape.objects.get(slug=landscape_slug)
        except Exception as error:
            logger.error(
                "Attempt to save Landscape Memberships, but landscape was not found",
                extra={
                    "landscape_slug": landscape_slug,
                    "error": error,
                },
            )
            raise GraphQLNotFoundException(model_name=Landscape.__name__)

        def validate(context):
            if not rules.test_rule(
                "allowed_to_change_landscape_membership",
                user,
                {
                    "landscape": landscape,
                    **context,
                },
            ):
                raise ValidationError("User cannot request membership")

        try:
            memberships = [
                {
                    "membership": result[1],
                    "context": result[0],
                }
                for email in kwargs["user_emails"]
                for result in [
                    landscape.membership_list.save_membership(
                        user_email=email,
                        user_role=kwargs["user_role"],
                        membership_status=CollaborationMembership.APPROVED,
                        validation_func=validate,
                    )
                ]
            ]
        except ValidationError as error:
            logger.error(
                "Attempt to save Landscape Memberships, but user is not allowed",
                extra={"error": str(error)},
            )
            raise GraphQLNotAllowedException(
                model_name=CollaborationMembership.__name__, operation=MutationTypes.UPDATE
            )
        except IntegrityError as exc:
            logger.info(
                "Attempt to save Landscape Memberships, but it's not unique",
                extra={"model": CollaborationMembership.__name__, "integrity_error": exc},
            )

            validation_error = ValidationError(
                message={
                    NON_FIELD_ERRORS: ValidationError(
                        message=f"This {CollaborationMembership.__name__} already exists",
                        code="unique",
                    )
                },
            )
            raise GraphQLValidationException.from_validation_error(
                validation_error, model_name=CollaborationMembership.__name__
            )
        except Exception as error:
            logger.error(
                "Attempt to update Story Map Memberships, but there was an error",
                extra={"error": str(error)},
            )
            raise GraphQLNotFoundException(model_name=CollaborationMembership.__name__)

        return cls(
            memberships=[membership["membership"] for membership in memberships],
            landscape=landscape,
        )


class LandscapeMembershipDeleteMutation(BaseDeleteMutation):
    membership = graphene.Field(CollaborationMembershipNode)
    landscape = graphene.Field(LandscapeNode)

    model_class = CollaborationMembership

    class Input:
        id = graphene.ID(required=True)
        landscape_slug = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        membership_id = kwargs["id"]
        landscape_slug = kwargs["landscape_slug"]

        try:
            landscape = Landscape.objects.get(slug=landscape_slug)
        except Landscape.DoesNotExist:
            logger.error(
                "Attempt to delete Landscape Membership, but landscape was not found",
                extra={"landscape_slug": landscape_slug},
            )
            raise GraphQLNotFoundException(model_name=Landscape.__name__)

        try:
            membership = landscape.membership_list.memberships.get(id=membership_id)
        except CollaborationMembership.DoesNotExist:
            logger.error(
                "Attempt to delete Landscape Membership, but membership was not found",
                extra={"membership_id": membership_id},
            )
            raise GraphQLNotFoundException(model_name=CollaborationMembership.__name__)

        if not rules.test_rule(
            "allowed_to_delete_landscape_membership",
            user,
            {
                "landscape": landscape,
                "membership": membership,
            },
        ):
            logger.info(
                "Attempt to delete Landscape Memberships, but user lacks permission",
                extra={"user_id": user.pk, "membership_id": membership_id},
            )
            raise GraphQLNotAllowedException(
                model_name=CollaborationMembership.__name__, operation=MutationTypes.DELETE
            )

        if not rules.test_rule(
            "allowed_landscape_managers_count",
            user,
            {
                "landscape": landscape,
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
        return cls(membership=result.membership, landscape=landscape)
