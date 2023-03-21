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
from graphene import relay
from graphene_django import DjangoObjectType

from apps.core.models import User, UserPreference
from apps.graphql.exceptions import GraphQLNotAllowedException

from .commons import BaseDeleteMutation, BaseMutation, TerrasoConnection
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class UserNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = User
        filter_fields = {
            "email": ["exact", "icontains"],
            "first_name": ["icontains"],
            "last_name": ["icontains"],
        }
        fields = ("email", "first_name", "last_name", "profile_image", "memberships", "preferences")
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


class UserPreferenceNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = UserPreference
        fields = ("key", "value", "user")
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection


class UserAddMutation(BaseMutation):
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


class UserUpdateMutation(BaseMutation):
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


class UserPreferenceUpdate(BaseMutation):
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

        preference.value = value
        preference.save()

        return cls(preference=preference)


class UserPreferenceDelete(BaseMutation):
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
        preference, _ = UserPreference.objects.get(user_id=user.id, key=key)

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

        preference.delete()

        return cls(preference=preference)
