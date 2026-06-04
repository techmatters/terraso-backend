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
from apps.collaboration.models import Membership
from apps.core.hubspot import create_account_deletion_ticket
from apps.core.models import User, UserPreference
from apps.core.models.users import USER_PREFS_KEY_ACCOUNT_DELETION, USER_PREFS_KEYS
from apps.graphql.exceptions import GraphQLNotAllowedException

from .commons import (
    BaseAdminMutation,
    BaseAuthenticatedMutation,
    BaseDeleteMutation,
    BaseUnauthenticatedMutation,
    TerrasoConnection,
)
from .constants import MutationTypes

logger = structlog.get_logger(__name__)


class UserFilter(FilterSet):
    # Substring filters (`email__icontains`, `first_name__icontains`,
    # `last_name__icontains`) can be used to harvest the user table — e.g.
    # `users(email_Icontains: "@target.com")` returns every account at a
    # given domain.  No production client uses them: web/mobile/shared all
    # call only `users(email)` or `users(email_Iexact: ...)` for the
    # userProfile and add-team-member flows (verified by grep against
    # terraso-web-client, terraso-mobile-client, terraso-client-shared).
    #
    # The substring filters are kept in the schema for potential future
    # admin/support workflows but are gated to `is_superuser=True` callers
    # in `qs` below.  Non-superuser callers using these filters get
    # `.none()` rather than an error: an empty result keeps the schema
    # response valid for any client that fires a substring filter
    # accidentally, and avoids surfacing "you would need superuser to do
    # this" as introspection-equivalent metadata.
    ADMIN_ONLY_FILTERS = ("email__icontains", "first_name__icontains", "last_name__icontains")

    # Exact-address lookups the production clients depend on: `userProfile`
    # uses `email`, and the add-member existence check uses `email_Iexact`
    # (optionally alongside `project`).  Each resolves a single, already-known
    # address — a one-at-a-time existence oracle, not an enumeration vector —
    # so it stays open to any authenticated caller.  Anything else (unfiltered,
    # `project`-only, or a substring filter) is a list/enumeration request and
    # is denied for non-superusers in `qs`.
    EXACT_EMAIL_FILTERS = ("email", "email__iexact")

    project = CharFilter(method="filter_user_in_project")

    class Meta:
        model = User
        fields = {
            "email": ["exact", "icontains", "iexact"],
            "first_name": ["icontains"],
            "last_name": ["icontains"],
        }

    def filter_user_in_project(self, queryset, name, value):
        memberships = Membership.objects.filter(membership_list__project=value)
        return queryset.filter(collaboration_memberships__in=memberships)

    @property
    def qs(self):
        # Default-deny enumeration of the user table.  Any authenticated caller
        # can self-register (open OAuth signup), so "authenticated" is a near-
        # public bar; without this gate an account could page the whole `users`
        # connection (or `users(project: ...)`) and harvest every email, name,
        # and membership.  `self.data` is the dict of incoming filter args keyed
        # by their Django ORM lookup name (e.g. "email__iexact").
        base = super().qs
        user = getattr(self.request, "user", None) if self.request else None
        if user and user.is_superuser:
            return base
        # Substring filters can harvest the table; superuser only (handled
        # above).  Checked before the exact-email allowlist so that combining a
        # substring with an exact email can't slip past the superuser gate.
        if any(self.data.get(name) for name in self.ADMIN_ONLY_FILTERS):
            return base.none()
        # Non-superusers may only resolve a single known address (the clients'
        # userProfile / add-member existence flows).  Returning `.none()` rather
        # than raising keeps the response schema-valid for a client that fires a
        # broad filter and avoids surfacing "superuser required" as metadata.
        if any(self.data.get(name) for name in self.EXACT_EMAIL_FILTERS):
            return base
        return base.none()


class UserNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = User
        filterset_class = UserFilter
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection
        fields = ("email", "first_name", "last_name", "profile_image", "memberships", "preferences")

    @classmethod
    def get_queryset(cls, queryset, info):
        # F1: anonymous users must not enumerate the user table or look up
        # users by id.  Authenticated, non-enumerating access (the clients'
        # userProfile / add-member existence lookups) is allowed; broader
        # enumeration by authenticated callers is denied in `UserFilter.qs`,
        # which — unlike get_queryset — can see the incoming filter args.
        if info.context.user.is_anonymous:
            return queryset.none()
        return queryset


class UserPreferenceNode(DjangoObjectType):
    id = graphene.ID(source="pk", required=True)

    class Meta:
        model = UserPreference
        fields = ("key", "value", "user")
        interfaces = (relay.Node,)
        connection_class = TerrasoConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        # Preferences (language, notification opt-ins, account-deletion-request)
        # are personal data. A caller may read only their own — the userProfile
        # flow fetches the logged-in user's own preferences — while superusers
        # keep full read access for admin/support. This stops the exact-email
        # lookup (`users(email: ...)`) from disclosing another user's
        # preferences via the nested `preferences` connection. Anonymous
        # callers (already blocked from UserNode) see nothing here too.
        user = info.context.user
        if user.is_anonymous:
            return queryset.none()
        if user.is_superuser:
            return queryset
        return queryset.filter(user=user)


# NOTE: Consider removing this mutation entirely. The legitimate user-creation
# paths in production are /auth/token-exchange (OAuth → JWT bridge) and the
# Django admin UI. A grep across web-client, mobile-client, client-shared and
# techmatters scripts found no callers of this mutation; only the test in
# test_user_mutations.py exercises it. Restricted to superuser/admin in the
# meantime so a non-admin authenticated account can't mint arbitrary users.
class UserAddMutation(BaseAdminMutation):
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

        if key not in USER_PREFS_KEYS:
            logger.error(
                "Attempt to update a User preferences, key not allowed",
                extra={"request_user_id": request_user.id, "target_user_id": user.id, "key": key},
            )
            raise GraphQLNotAllowedException(
                model_name=UserPreference.__name__, operation=MutationTypes.UPDATE
            )

        previous_value = preference.value
        preference.value = value
        preference.save()

        if (
            key == USER_PREFS_KEY_ACCOUNT_DELETION
            and previous_value.lower() != "true"
            and value.lower() == "true"
        ):
            create_account_deletion_ticket(user)

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

        if key not in USER_PREFS_KEYS:
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

        for notification_key in USER_PREFS_KEYS:
            preference, _ = UserPreference.objects.get_or_create(
                user_id=user.id, key=notification_key
            )
            preference.value = "false"
            preference.save()

        return cls(success=True)
