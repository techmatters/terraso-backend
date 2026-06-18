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

from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserCreationForm
from django.utils.html import format_html

from apps.auth.services import JWTService

from .models import (
    Group,
    Landscape,
    LandscapeDevelopmentStrategy,
    LandscapeGroup,
    SharedResource,
    TaxonomyTerm,
    User,
    UserPreference,
)


def create_partner_refresh_token(user, ttl: timedelta) -> str:
    # Long-lived refresh token for partner / service-account API access (2a).
    # The partner exchanges it at /auth/tokens for short-lived access tokens.
    # Revoke by unchecking "Active" on the user: RefreshAccessTokenView rejects
    # refresh for inactive users, so no new access tokens can be minted (existing
    # access tokens expire within JWT_ACCESS_EXP_DELTA_SECONDS).
    # `service_account` marks this as a long-lived partner/service credential so
    # analytics can exclude it from human active-user counts (see docs/posthog.md §5).
    return JWTService().create_token(
        user,
        expiration=int(ttl.total_seconds()),
        extra_payload={"refresh": True, "service_account": True},
    )


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "website", "created_at")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.exclude(associated_landscapes__is_default_landscape_group=True)


@admin.register(Landscape)
class LandscapeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "location", "website", "created_at")
    raw_id_fields = ("membership_list",)


class LandscapeDefaultGroup(Group):
    class Meta:
        proxy = True


@admin.register(LandscapeGroup)
class LandscapeGroupAdmin(admin.ModelAdmin):
    list_display = ("landscape", "group")


class UserPreferenceInline(admin.TabularInline):
    model = UserPreference


class UserAdminCreationForm(UserCreationForm):
    # Django's default UserCreationForm is tied to a `username` field; this
    # User model is email-based (USERNAME_FIELD = "email", username removed),
    # so bind the creation form to email instead.
    class Meta:
        model = User
        fields = ("email",)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "created_at", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    inlines = [UserPreferenceInline]
    readonly_fields = ["id"]
    add_form = UserAdminCreationForm
    # DjangoUserAdmin's default add_fieldsets references `username`, which this
    # model doesn't have — override it to the email-based creation fields.
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)
    actions = ["mint_partner_refresh_token_10y", "mint_partner_refresh_token_1y"]

    @admin.action(description="Mint 10-year partner refresh token (API / soil-ID access)")
    def mint_partner_refresh_token_10y(self, request, queryset):
        self._mint_partner_refresh_token(request, queryset, timedelta(days=365 * 10), "10 years")

    @admin.action(description="Mint 1-year partner refresh token (API / soil-ID access)")
    def mint_partner_refresh_token_1y(self, request, queryset):
        self._mint_partner_refresh_token(request, queryset, timedelta(days=365), "1 year")

    def _mint_partner_refresh_token(self, request, queryset, ttl, ttl_label):
        # Issue one token for a single, deliberately-selected user — intended
        # for a dedicated service account, not a real person's login.
        if queryset.count() != 1:
            self.message_user(
                request,
                "Select exactly one user (ideally a dedicated service account).",
                level=messages.ERROR,
            )
            return

        user = queryset.first()
        token = create_partner_refresh_token(user, ttl)
        # Surfaced once in the admin UI for the operator to copy. Never logged
        # or persisted (secrets policy): there is no server-side record of the
        # token value, which is why it cannot be re-displayed later.
        self.message_user(
            request,
            format_html(
                "Refresh token for <b>{}</b> (valid {}). Copy it now — it is not "
                "stored and cannot be shown again:<br><code>{}</code><br>"
                'Revoke later by unchecking "Active" on this user.',
                user.email,
                ttl_label,
                token,
            ),
            level=messages.WARNING,
        )

    fieldsets = (
        (None, {"fields": ("email", "id", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )


@admin.register(TaxonomyTerm)
class TaxonomyTermAdmin(admin.ModelAdmin):
    list_display = ("value_original", "type", "value_en", "value_es")


@admin.register(LandscapeDevelopmentStrategy)
class LandscapeDevelopmentStrategyAdmin(admin.ModelAdmin):
    list_display = ("id", "landscape")


@admin.register(SharedResource)
class SharedResourceAdmin(admin.ModelAdmin):
    list_display = ("id", "share_uuid", "share_access")
