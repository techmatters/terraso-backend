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

# Register your models here.
from django.contrib import admin
from safedelete.admin import SafeDeleteAdmin, SafeDeleteAdminFilter, highlight_deleted

from apps.project_management.models import Project, Site, SiteNote, SitePushHistory


@admin.register(Project)
class ProjectAdmin(SafeDeleteAdmin):
    readonly_fields = ("membership_list", "deleted_at")
    list_display = (
        highlight_deleted,
        "name",
        "privacy",
        "archived",
        "deleted_at",
        "created_at",
    )
    list_filter = (SafeDeleteAdminFilter, "privacy", "archived")
    search_fields = ("name",)


@admin.register(Site)
class SiteAdmin(SafeDeleteAdmin):
    readonly_fields = ("deleted_at",)
    list_display = (
        highlight_deleted,
        "name",
        "owner",
        "project__name",
        "privacy",
        "archived",
        "deleted_at",
        "created_at",
    )
    list_filter = (SafeDeleteAdminFilter, "privacy", "archived")
    search_fields = ("name", "owner__email", "project__name")


@admin.register(SitePushHistory)
class SitePushHistoryAdmin(SafeDeleteAdmin):
    readonly_fields = ("deleted_at",)
    list_display = [
        highlight_deleted,
        "updated_at",
        "site__name",
        "changed_by__email",
        "update_succeeded",
        "deleted_at",
        "update_failure_reason",
    ]
    list_filter = (SafeDeleteAdminFilter, "update_succeeded")
    search_fields = ["site__name", "changed_by__email", "update_succeeded", "update_failure_reason"]


@admin.register(SiteNote)
class SiteNoteAdmin(SafeDeleteAdmin):
    readonly_fields = ("deleted_at",)
    list_display = (
        highlight_deleted,
        "site__name",
        "author__email",
        "deleted_at",
        "created_at",
    )
    list_filter = (SafeDeleteAdminFilter,)
    search_fields = ("site__name", "author__email", "content")
