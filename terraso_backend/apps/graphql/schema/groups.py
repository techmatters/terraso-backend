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

import django_filters
import graphene
import rules
import structlog
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError, transaction
from graphene import relay
from graphene_django import DjangoObjectType

from apps.collaboration.graphql import CollaborationMembershipNode
from apps.collaboration.models import Membership as CollaborationMembership
from apps.collaboration.models import MembershipList
from apps.core import group_collaboration_roles
from apps.core.models import Group
from apps.graphql.exceptions import (
    GraphQLNotAllowedException,
    GraphQLNotFoundException,
    GraphQLValidationException,
)
from apps.notifications.email import EmailNotification

from .commons import (
    BaseAuthenticatedMutation,
    BaseDeleteMutation,
    BaseWriteMutation,
    TerrasoConnection,
)
from .constants import MutationTypes
from .shared_resources_mixin import SharedResourcesMixin

logger = structlog.get_logger(__name__)


class GroupFilterSet(django_filters.FilterSet):
    memberships__email = django_filters.CharFilter(method="filter_memberships_email")
    associated_landscapes__isnull = django_filters.BooleanFilter(
        method="filter_associated_landscapes"
    )
    associated_landscapes__is_partnership = django_filters.BooleanFilter(
        method="filter_associated_landscapes"
    )

    class Meta:
        model = Group
        fields = {
            "name": ["exact", "icontains", "istartswith"],
            "slug": ["exact", "icontains"],
            "description": ["icontains"],
        }

    def filter_memberships_email(self, queryset, name, value):
        return queryset.filter(
            membership_list__memberships__user__email=value,
            membership_list__memberships__deleted_at__isnull=True,
        )

    def filter_associated_landscapes(self, queryset, name, value):
        filters = {"associated_landscapes__deleted_at__isnull": True}
        filters[name] = value
        # TODO Removed duplicated group results using order_by('slug').distinct('slug')
        # Is there a better way to do this?
        return queryset.filter(**filters).order_by("slug").distinct("slug")


class GroupNode(DjangoObjectType, SharedResourcesMixin):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = Group
        fields = (
            "name",
            "slug",
            "description",
            "website",
            "email",
            "created_by",
            "membership_list",
            "associations_as_parent",
            "associations_as_child",
            "associated_landscapes",
        )
        filterset_class = GroupFilterSet
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        return queryset.exclude(
            associated_landscapes__is_default_landscape_group=True,
        )

    # def resolve_account_membership(self, info):
    #     user = info.context.user
    #     if user.is_anonymous:
    #         return None
    #     if hasattr(self, "account_memberships"):
    #         if len(self.account_memberships) > 0:
    #             return self.account_memberships[0]
    #         return None
    #     return self.memberships.filter(user=user).first()

    # def resolve_memberships_count(self, info):
    #     if hasattr(self, "memberships_count"):
    #         return self.memberships_count

    #     # Nonmembers cannot see the number of members of a closed group
    #     if self.membership_type == Group.MEMBERSHIP_TYPE_CLOSED:
    #         is_member = (
    #             self.memberships.approved_only().filter(user__id=info.context.user.pk).exists()
    #         )
    #         if not is_member:
    #             return 0

    #     return self.memberships.approved_only().count()


class GroupAddMutation(BaseWriteMutation):
    group = graphene.Field(GroupNode)

    model_class = Group

    class Input:
        name = graphene.String(required=True)
        description = graphene.String()
        website = graphene.String()
        email = graphene.String()
        membership_type = graphene.String()

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        if not cls.is_update(kwargs):
            kwargs["created_by"] = user

        result = super().mutate_and_get_payload(root, info, **kwargs)

        group = result.group

        if "membership_type" in kwargs:
            group.membership_list.membership_type = MembershipList.get_membership_type_from_text(
                kwargs["membership_type"]
            )
            group.membership_list.save()

        return cls(group=group)


class GroupUpdateMutation(BaseWriteMutation):
    group = graphene.Field(GroupNode)

    model_class = Group

    class Input:
        id = graphene.ID(required=True)
        name = graphene.String()
        description = graphene.String()
        website = graphene.String()
        email = graphene.String()
        membership_type = graphene.String()

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        group_id = kwargs["id"]

        if not user.has_perm(Group.get_perm("change"), obj=group_id):
            logger.info(
                "Attempt to update a Group, but user has no permission",
                extra={"user_id": user.pk, "group_id": group_id},
            )
            raise GraphQLNotAllowedException(
                model_name=Group.__name__, operation=MutationTypes.UPDATE
            )

        result = super().mutate_and_get_payload(root, info, **kwargs)

        group = result.group

        if "membership_type" in kwargs:
            group.membership_list.membership_type = MembershipList.get_membership_type_from_text(
                kwargs["membership_type"]
            )
            group.membership_list.save()

        return cls(group=group)


class GroupDeleteMutation(BaseDeleteMutation):
    group = graphene.Field(GroupNode)
    model_class = Group

    class Input:
        id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user
        group_id = kwargs["id"]

        if not user.has_perm(Group.get_perm("delete"), obj=group_id):
            logger.info(
                "Attempt to delete a Group, but user has no permission",
                extra={"user_id": user.pk, "group_id": group_id},
            )
            raise GraphQLNotAllowedException(
                model_name=Group.__name__, operation=MutationTypes.DELETE
            )

        return super().mutate_and_get_payload(root, info, **kwargs)


class GroupMembershipSaveMutation(BaseAuthenticatedMutation):
    model_class = CollaborationMembership
    memberships = graphene.Field(graphene.List(CollaborationMembershipNode))
    group = graphene.Field(GroupNode)

    class Input:
        user_role = graphene.String(required=True)
        user_emails = graphene.List(graphene.String, required=True)
        group_slug = graphene.String(required=True)

    @classmethod
    @transaction.atomic
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = info.context.user

        if kwargs["user_role"] not in group_collaboration_roles.ALL_ROLES:
            logger.info(
                "Attempt to save Group Memberships, but user role is not valid",
                extra={
                    "user_role": kwargs["user_role"],
                },
            )
            raise GraphQLNotAllowedException(
                model_name=CollaborationMembership.__name__, operation=MutationTypes.UPDATE
            )

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

        def validate(context):
            if not rules.test_rule(
                "allowed_to_change_group_membership",
                user,
                {
                    "group": group,
                    **context,
                },
            ):
                raise ValidationError("User cannot request membership")

        is_closed_group = (
            group.membership_list.membership_type == MembershipList.MEMBERSHIP_TYPE_CLOSED
        )

        try:
            memberships = [
                {
                    "membership": result[1],
                    "was_approved": result[0],
                }
                for email in kwargs["user_emails"]
                for result in [
                    group.membership_list.save_membership(
                        user_email=email,
                        user_role=kwargs["user_role"],
                        membership_status=CollaborationMembership.PENDING
                        if is_closed_group
                        else CollaborationMembership.APPROVED,
                        validation_func=validate,
                    )
                ]
            ]
        except ValidationError as error:
            logger.error(
                "Attempt to save Group Memberships, but user is not allowed",
                extra={"error": str(error)},
            )
            raise GraphQLNotAllowedException(
                model_name=CollaborationMembership.__name__, operation=MutationTypes.UPDATE
            )
        except IntegrityError as exc:
            logger.info(
                "Attempt to save Group Memberships, but it's not unique",
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

        if group.membership_list.membership_type == MembershipList.MEMBERSHIP_TYPE_CLOSED:
            for membership in memberships:
                if not membership["was_approved"]:
                    EmailNotification.send_membership_request(membership["membership"].user, group)

        return cls(
            memberships=[membership["membership"] for membership in memberships],
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
