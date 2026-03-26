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

from apps.project_management.models import Project, ProjectSettings, Site, SitePushHistory

admin.site.register(ProjectSettings)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    readonly_fields = ("membership_list", "settings")
    list_display = ("name", "created_at")


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "project__name", "created_at")
    search_fields = ("name", "owner", "project__name")


@admin.register(SitePushHistory)
class SitePushHistoryAdmin(admin.ModelAdmin):
    list_display = [
        "updated_at",
        "site__name",
        "changed_by__email",
        "update_succeeded",
        "update_failure_reason",
    ]
    search_fields = ["site__name", "changed_by__email", "update_succeeded", "update_failure_reason"]
