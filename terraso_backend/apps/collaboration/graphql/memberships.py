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
from django.db import IntegrityError
from graphene import relay
from graphene_django import DjangoObjectType

from apps.collaboration.models import Membership, MembershipList
from apps.graphql.exceptions import (
    GraphQLNotAllowedException,
    GraphQLNotFoundException,
    GraphQLValidationException,
)
from apps.graphql.schema.commons import BaseAuthenticatedMutation
from apps.graphql.schema.constants import MutationTypes

logger = structlog.get_logger(__name__)


# TODO: trying to import this from apps.graphql.schema.commons causes a circular import
# Created an issue to move the module to apps.graphql.commons, as that seems simplest
# https://github.com/techmatters/terraso-backend/issues/820
class TerrasoConnection(graphene.Connection):
    class Meta:
        abstract = True

    total_count = graphene.Int(required=True)

    def resolve_total_count(self, info, **kwargs):
        queryset = self.iterable
        return queryset.count()

    @classmethod
    def __init_subclass_with_meta__(cls, **options):
        options["strict_types"] = options.pop("strict_types", True)
        super().__init_subclass_with_meta__(**options)


class MembershipListNodeMixin:
    id = graphene.ID(source="pk", required=True)
    account_membership = graphene.Field("apps.collaboration.graphql.CollaborationMembershipNode")
    memberships_count = graphene.Int()

    class Meta:
        model = MembershipList
        fields = (
            "memberships",
            "membership_type",
            "enroll_method",
        )
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    def resolve_account_membership(self, info):
        user = info.context.user
        if user.is_anonymous:
            return None
        if hasattr(self, "account_memberships"):
            if len(self.account_memberships):
                return self.account_memberships[0]
            return None
        return self.memberships.filter(user=user).first()

    def resolve_memberships_count(self, info):
        if hasattr(self, "memberships_count"):
            return self.memberships_count
        user = info.context.user
        if user.is_anonymous:
            return 0
        return self.memberships.approved_only().count()


class CollaborationMembershipListNode(MembershipListNodeMixin, DjangoObjectType):
    class Meta(MembershipListNodeMixin.Meta):
        pass


class CollaborationMembershipFilterSet(django_filters.FilterSet):
    user__email__not = django_filters.CharFilter(method="filter_user_email_not")

    class Meta:
        model = Membership
        fields = {
            "user": ["exact", "in"],
            "user_role": ["exact"],
            "user__email": ["icontains", "in"],
            "membership_status": ["exact"],
        }

    def filter_user_email_not(self, queryset, name, value):
        return queryset.exclude(user__email=value)


class MembershipNodeMixin:
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = Membership
        fields = ("membership_list", "user", "user_role", "membership_status", "pending_email")
        filterset_class = CollaborationMembershipFilterSet
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        user = info.context.user
        if user.is_anonymous:
            return queryset.none()

        return queryset


class CollaborationMembershipNode(MembershipNodeMixin, DjangoObjectType):
    class Meta(MembershipNodeMixin.Meta):
        pass


class BaseMembershipSaveMutation(BaseAuthenticatedMutation):
    @classmethod
    def validate_role(cls, role, accepted_roles):
        if role not in accepted_roles:
            logger.info(
                "Attempt to save Memberships, but user role is not valid",
                extra={
                    "user_role": role,
                    "accepted_roles": accepted_roles,
                },
            )
            raise GraphQLNotAllowedException(
                model_name=Membership.__name__, operation=MutationTypes.UPDATE
            )

    @classmethod
    def save_memberships(cls, user, validation_rule, validation_context, membership_list, kwargs):
        def validate(context):
            if not rules.test_rule(
                validation_rule,
                user,
                {
                    **context,
                    **validation_context,
                },
            ):
                raise ValidationError("User cannot request membership")

        try:
            return [
                {
                    "membership": result[1],
                    "context": result[0],
                }
                for email in kwargs["user_emails"]
                for result in [
                    membership_list.save_membership(
                        user_email=email,
                        user_role=kwargs["user_role"],
                        membership_status=kwargs["membership_status"],
                        validation_func=validate,
                    )
                ]
            ]
        except ValidationError as error:
            logger.error(
                "Attempt to save Memberships, but user is not allowed",
                extra={"error": str(error)},
            )
            raise GraphQLNotAllowedException(
                model_name=Membership.__name__, operation=MutationTypes.UPDATE
            )
        except IntegrityError as exc:
            logger.info(
                "Attempt to save Memberships, but it's not unique",
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
                "Attempt to update Memberships, but there was an error",
                extra={"error": str(error)},
            )
            raise GraphQLNotFoundException(model_name=Membership.__name__)
