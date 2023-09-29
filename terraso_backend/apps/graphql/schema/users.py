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
import rules
import structlog
from django_filters import CharFilter, FilterSet
from graphene import relay
from graphene_django import DjangoObjectType

from apps.auth.services import JWTService
from apps.core.models import User, UserPreference
from apps.core.models.users import NOTIFICATION_KEYS
from apps.graphql.exceptions import GraphQLNotAllowedException

from .commons import (
    BaseAuthenticatedMutation,
    BaseDeleteMutation,
    BaseUnauthenticatedMutation,
    TerrasoConnection,
)
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class UserFilter(FilterSet):
    user__in_project = CharFilter(method="filter_user_in_project")

    class Meta:
        model = User
        fields = {
            "email": ["exact", "icontains"],
            "first_name": ["icontains"],
            "last_name": ["icontains"],
        }

    def filter_user_in_project(self, queryset, name, value):
        return queryset.filter(collaboration_memberships__membership_list__project__id=value)


class UserNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = User
        filterset_class = UserFilter
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection
        fields = ("email", "first_name", "last_name", "profile_image", "memberships", "preferences")


class UserPreferenceNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = UserPreference
        fields = ("key", "value", "user")
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


class UserAddMutation(BaseAuthenticatedMutation):
    user = graphene.Field(UserNode)

    class Input:
        first_name = graphene.String()
        last_name = graphene.String()
        email = graphene.String(required=True)
        password = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        user = User.objects.create_user(
            kwargs.pop("email"), password=kwargs.pop("password"), **kwargs
        )

        return cls(user=user)


class UserUpdateMutation(BaseAuthenticatedMutation):
    user = graphene.Field(UserNode)

    model_class = User

    class Input:
        id = graphene.ID(required=True)
        first_name = graphene.String()
        last_name = graphene.String()
        email = graphene.String()
        password = graphene.String()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        request_user = info.context.user
        _id = kwargs.pop("id")

        if str(request_user.id) != _id:
            logger.error(
                "Attempt to update a User by another user, not allowed",
                extra={"request_user_id": request_user.id, "target_user_id": _id},
            )
            raise GraphQLNotAllowedException(
                model_name=User.__name__, operation=MutationTypes.UPDATE
            )

        user = User.objects.get(pk=_id)
        new_password = kwargs.pop("password", None)

        if new_password:
            user.set_password(new_password)

        for attr, value in kwargs.items():
            setattr(user, attr, value)

        user.save()

        return cls(user=user)


class UserDeleteMutation(BaseDeleteMutation):
    user = graphene.Field(UserNode)
    model_class = User

    class Input:
        id = graphene.ID()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        request_user = info.context.user
        _id = kwargs.get("id")

        if str(request_user.id) != _id:
            logger.error(
                "Attempt to delete a User by another user, not allowed",
                extra={"request_user_id": request_user.id, "target_user_id": _id},
            )
            raise GraphQLNotAllowedException(
                model_name=User.__name__, operation=MutationTypes.DELETE
            )

        return super().mutate_and_get_payload(root, info, **kwargs)


class UserPreferenceUpdate(BaseAuthenticatedMutation):
    preference = graphene.Field(UserPreferenceNode)

    model_class = UserPreference

    class Input:
        user_email = graphene.String(required=True)
        key = graphene.String(required=True)
        value = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        request_user = info.context.user
        user_email = kwargs.pop("user_email")
        key = kwargs.pop("key")
        value = kwargs.pop("value")
        user = User.objects.get(email=user_email)
        preference, _ = UserPreference.objects.get_or_create(user_id=user.id, key=key)

        if not rules.test_rule("allowed_to_update_preferences", request_user, preference):
            logger.error(
                "Attempt to update a User preferences, not allowed",
                extra={"request_user_id": request_user.id, "target_user_id": user.id},
            )
            raise GraphQLNotAllowedException(
                model_name=UserPreference.__name__, operation=MutationTypes.UPDATE
            )

        if key not in NOTIFICATION_KEYS:
            logger.error(
                "Attempt to update a User preferences, key not allowed",
                extra={"request_user_id": request_user.id, "target_user_id": user.id, "key": key},
            )
            raise GraphQLNotAllowedException(
                model_name=UserPreference.__name__, operation=MutationTypes.UPDATE
            )

        preference.value = value
        preference.save()

        return cls(preference=preference)


class UserPreferenceDelete(BaseAuthenticatedMutation):
    preference = graphene.Field(UserPreferenceNode)

    model_class = UserPreference

    class Input:
        user_email = graphene.String(required=True)
        key = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        request_user = info.context.user
        user_email = kwargs.pop("user_email")
        key = kwargs.pop("key")
        user = User.objects.get(email=user_email)
        preference = UserPreference.objects.get(user_id=user.id, key=key)

        if not rules.test_rule("allowed_to_update_preferences", request_user, preference):
            logger.error(
                "Attempt to delete a User preferences, not allowed",
                extra={"request_user_id": request_user.id, "target_user_id": user.id},
            )
            raise GraphQLNotAllowedException(
                model_name=UserPreference.__name__, operation=MutationTypes.DELETE
            )

        if not preference:
            logger.error(
                "Attempt to delete a User preferences, does not exist",
                extra={"request_user_id": request_user.id, "target_user_id": user.id},
            )
            raise GraphQLNotAllowedException(
                model_name=UserPreference.__name__, operation=MutationTypes.DELETE
            )

        if key not in NOTIFICATION_KEYS:
            logger.error(
                "Attempt to delete a User preferences, key not allowed",
                extra={"request_user_id": request_user.id, "target_user_id": user.id, "key": key},
            )
            raise GraphQLNotAllowedException(
                model_name=UserPreference.__name__, operation=MutationTypes.DELETE
            )

        preference.delete()

        return cls(preference=preference)


class UserUnsubscribeUpdate(BaseUnauthenticatedMutation):
    success = graphene.Boolean()

    model_class = UserPreference

    class Input:
        token = graphene.String(required=True)

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        token = kwargs.pop("token")

        try:
            decoded_payload = JWTService().verify_unsubscribe_token(token)
        except Exception:
            logger.exception("Failure to verify JWT token", extra={"token": token})
            raise GraphQLNotAllowedException(
                model_name=UserPreference.__name__, operation=MutationTypes.UPDATE
            )

        user = User.objects.get(pk=decoded_payload["sub"])

        if not user:
            logger.error(
                "Attempt to update a User preferences, user does not exist",
                extra={"user_id": user.id},
            )
            raise GraphQLNotAllowedException(
                model_name=UserPreference.__name__, operation=MutationTypes.UPDATE
            )

        for notification_key in NOTIFICATION_KEYS:
            preference, _ = UserPreference.objects.get_or_create(
                user_id=user.id, key=notification_key
            )
            preference.value = "false"
            preference.save()

        return cls(success=True)
