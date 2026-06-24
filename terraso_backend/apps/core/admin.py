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

from django.apps import apps
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html, format_html_join
from safedelete.admin import SafeDeleteAdmin, SafeDeleteAdminFilter, highlight_deleted

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
from .models.users import _format_blocker


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


@admin.register(User)
class UserAdmin(SafeDeleteAdmin, DjangoUserAdmin):
    # Mixing SafeDeleteAdmin gives:
    #   - List queryset that includes soft-deleted users (visible alongside
    #     active ones).
    #   - "highlight_deleted" indicator in the list display.
    #   - Filter to slice the list by Active / Deleted / All.
    #   - Bulk actions: "undelete_selected" (recover) and
    #     "hard_delete_soft_deleted" (purge — same as the harddelete cron).
    #
    # Undelete restores the User row plus soft-deleted related rows
    # (Memberships) and re-attaches DataEntry.created_by. It does NOT
    # recover SiteNote.author or Site.owner that were nulled by SET_NULL;
    # those notes/sites remain permanently attributed to "Deleted User"
    # (the stub) even after undelete. See user_deletion_lifecycle.md
    # and account_deletion_author_snapshot_plan.md in
    # terraso-backend-research for context and possible follow-ups.
    #
    # Email-collision safety: User.undelete() refuses if the email is
    # taken by another active user (admin will surface a ValidationError),
    # which would otherwise hit the conditional unique_active_email
    # constraint and produce a less-helpful IntegrityError.
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
        """Replace Django's collector-based "protected related objects" list
        with our own from deletion_blockers(). Django over-lists (includes
        soft-deleted PROTECT rows we consider non-blockers) and under-lists
        (skips DO_NOTHING rows we consider real blockers). Sourcing from
        deletion_blockers() makes the admin's confirmation page agree with
        the GraphQL UserDeleteMutation."""
        to_delete, model_count, perms_needed, _ = super().get_deleted_objects(objs, request)
        protected = []
        for obj in objs:
            for b in obj.deletion_blockers():
                protected.append(self._format_blocker_protected(b))
        return to_delete, model_count, perms_needed, protected

    @staticmethod
    def _format_blocker_protected(b):
        """Render a blocker for the admin's "protected related objects"
        list. IDs link to each row's admin change page when the model is
        admin-registered; falls back to plain text otherwise."""
        qualifier = format_html(" ({})", b["qualifier"]) if b.get("qualifier") else ""
        label = format_html("{}{} ({})", b["model"], qualifier, b["field"])
        ids = b.get("ids") or []
        count = b["count"]
        if not ids:
            return format_html("{}: {} row(s)", label, count)

        try:
            model = apps.get_model(b["model"])
            url_name = f"admin:{model._meta.app_label}_{model._meta.model_name}_change"
            ids_html = format_html_join(
                ", ", '<a href="{}">{}</a>', ((reverse(url_name, args=[pk]), pk) for pk in ids)
            )
        except (LookupError, NoReverseMatch):
            ids_html = format_html_join(", ", "{}", ((pk,) for pk in ids))

        extra = count - len(ids)
        if extra > 0:
            return format_html(
                "{}: {} row(s); first {} IDs: {} (+{} more)",
                label,
                count,
                len(ids),
                ids_html,
                extra,
            )
        return format_html("{}: {} row(s); IDs: {}", label, count, ids_html)

    def delete_model(self, request, obj):
        """Pre-check User.deletion_blockers() so staff get a readable banner
        instead of a raw ValidationError page when the user has undeletable
        data. The same gate also lives in User.delete() as a safety net."""
        blockers = obj.deletion_blockers()
        if blockers:
            self.message_user(
                request,
                self._format_blocker_message(obj, blockers),
                level=messages.ERROR,
            )
            return  # do not call super; user stays undeleted
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Bulk delete: partition into deletable/blocked, delete the clean
        ones individually, surface the skipped ones in a single banner.

        We iterate `user.delete()` per user rather than using the queryset
        delete so each user's soft_delete_policy_action runs (tearing down
        sole-manager projects)."""
        deletable, blocked = [], []
        for user in queryset:
            if user.deletion_blockers():
                blocked.append(user)
            else:
                deletable.append(user)
        for user in deletable:
            user.delete()
        if blocked:
            emails = ", ".join(u.email for u in blocked)
            self.message_user(
                request,
                f"Skipped {len(blocked)} user(s) with undeletable data: {emails}. "
                "These require manual cleanup before deletion.",
                level=messages.WARNING,
            )

    def _format_blocker_message(self, user, blockers):
        items = format_html_join("", "<li>{}: {}</li>", (_format_blocker(b) for b in blockers))
        return format_html(
            "Cannot delete user <strong>{}</strong>: user has undeletable "
            "data and must be cleaned up manually first.<ul>{}</ul>",
            user.email,
            items,
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
