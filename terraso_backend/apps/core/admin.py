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
from safedelete.admin import SafeDeleteAdmin, SafeDeleteAdminFilter, highlight_deleted

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
from .models.users import UserDeletionBlockedError


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
class GroupAdmin(SafeDeleteAdmin):
    list_display = (highlight_deleted, "slug", "website", "deleted_at", "created_at")
    list_filter = (SafeDeleteAdminFilter,)
    search_fields = ("name", "slug")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.exclude(associated_landscapes__is_default_landscape_group=True)


@admin.register(Landscape)
class LandscapeAdmin(SafeDeleteAdmin):
    list_display = (highlight_deleted, "slug", "location", "website", "deleted_at", "created_at")
    list_filter = (SafeDeleteAdminFilter,)
    search_fields = ("name", "slug", "location")
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
class UserAdmin(SafeDeleteAdmin, DjangoUserAdmin):
    ordering = ("email",)
    list_display = (
        highlight_deleted,  # module-level function from safedelete.admin
        "first_name",
        "last_name",
        "created_at",
        "is_staff",
    )
    list_filter = DjangoUserAdmin.list_filter + (SafeDeleteAdminFilter,)
    search_fields = ("email", "first_name", "last_name")
    inlines = [UserPreferenceInline]
    readonly_fields = ["id"]
    add_form = UserAdminCreationForm
    # DjangoUserAdmin's default add_fieldsets references `username`, which this
    # model doesn't have — override it to the email-based creation fields.
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)
    actions = [
        *SafeDeleteAdmin.actions,
        "mint_partner_refresh_token_10y",
        "mint_partner_refresh_token_1y",
    ]

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

    def get_deleted_objects(self, objs, request):
        """Never refuse at the confirmation-page level (`protected=[]` always)
        — `User.delete()` is the source of truth; `delete_model` /
        `delete_queryset` catch `UserDeletionBlockedError` and surface a
        "Skipped" warning banner. On the confirmation-page render, also fire
        a warning banner listing the actual blockers (via `deletion_blockers`,
        the same source `show_deletion_blockers` uses) so staff can preview
        why the delete will be skipped — with a pointer at the CLI for
        row-level detail.

        Gated on `not request.POST.get("post")` so the banner fires only on
        the confirmation-page render, not on the delete POST cycle (which
        would persist the banner through the post-delete redirect)."""
        from apps.core.management.commands.show_deletion_blockers import (
            deletion_blockers,
            format_blocker,
        )

        to_delete, model_count, perms_needed, _ = super().get_deleted_objects(objs, request)

        if objs and not request.POST.get("post"):
            summaries = []
            for obj in objs:
                for b in deletion_blockers(obj):
                    label, detail = format_blocker(b)
                    summaries.append(f"{label}: {detail}")
            if summaries:
                preview = "; ".join(summaries[:5])
                more = f" (+{len(summaries) - 5} more)" if len(summaries) > 5 else ""
                messages.warning(
                    request,
                    f"Deletion would be blocked by: {preview}{more}. "
                    "Run 'python manage.py show_deletion_blockers <email>' for row-level detail.",
                )

        return to_delete, model_count, perms_needed, []

    def message_user(
        self, request, message, level=messages.INFO, extra_tags="", fail_silently=False
    ):
        """Suppress Django's stock "was deleted successfully" / "Successfully
        deleted N users" message when we've partially or fully blocked the
        deletion. Django's success message is hardcoded off the queryset
        count (bulk) or fires unconditionally after delete_model (single),
        neither of which reflects reality if any user was skipped."""
        if level == messages.SUCCESS and getattr(request, "_deletion_was_blocked", False):
            return
        super().message_user(request, message, level, extra_tags, fail_silently)

    def delete_model(self, request, obj):
        """Catch UserDeletionBlockedError and surface a "Skipped" warning
        banner mirroring the bulk-delete phrasing. Marks the request so
        `message_user` suppresses Django's forthcoming "was deleted
        successfully" message from `response_delete`."""
        try:
            super().delete_model(request, obj)
        except UserDeletionBlockedError:
            request._deletion_was_blocked = True
            self.message_user(
                request,
                f"Skipped 1 user with undeletable data: {obj.email}. "
                "Run 'python manage.py show_deletion_blockers <email>' for details.",
                level=messages.WARNING,
            )

    def delete_queryset(self, request, queryset):
        """Bulk delete: iterate per-user so each user's cascade runs
        (solo-manager projects torn down individually), catching
        UserDeletionBlockedError so the batch keeps going. Marks the
        request when anything was skipped so `message_user` suppresses
        Django's "Successfully deleted N users" (which counts the whole
        queryset, not the actual deletions)."""
        blocked = []
        deleted = 0
        for user in queryset:
            try:
                user.delete()
                deleted += 1
            except UserDeletionBlockedError:
                blocked.append(user)
        if blocked:
            request._deletion_was_blocked = True
            emails = ", ".join(u.email for u in blocked)
            prefix = f"Deleted {deleted} user(s). " if deleted else ""
            self.message_user(
                request,
                f"{prefix}Skipped {len(blocked)} user(s) with undeletable data: {emails}. "
                "Run 'python manage.py show_deletion_blockers <email>' for details.",
                level=messages.WARNING,
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
