# Copyright © 2024 Technology Matters
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

from django.contrib import admin
from safedelete.admin import SafeDeleteAdmin, SafeDeleteAdminFilter, highlight_deleted

from apps.soil_id.models import (
    DepthDependentSoilData,
    ProjectDepthInterval,
    ProjectSoilSettings,
    SoilData,
    SoilDataDepthInterval,
    SoilDataHistory,
    SoilMetadata,
)
from apps.soil_id.models.soil_id_cache import SoilIdCache


class DepthDependentSoilDataInline(admin.TabularInline):
    model = DepthDependentSoilData
    extra = 0
    # Inlines show soft-deleted children alongside active ones
    fields = ("depth_interval_start", "depth_interval_end", "deleted_at")
    readonly_fields = ("deleted_at",)

    def get_queryset(self, request):
        return DepthDependentSoilData.objects.all_with_deleted()


class SoilDataDepthIntervalInline(admin.TabularInline):
    model = SoilDataDepthInterval
    extra = 0
    fields = ("depth_interval_start", "depth_interval_end", "deleted_at")
    readonly_fields = ("deleted_at",)

    def get_queryset(self, request):
        return SoilDataDepthInterval.objects.all_with_deleted()


class ProjectDepthIntervalInline(admin.TabularInline):
    model = ProjectDepthInterval
    extra = 0
    fields = ("depth_interval_start", "depth_interval_end", "deleted_at")
    readonly_fields = ("deleted_at",)

    def get_queryset(self, request):
        return ProjectDepthInterval.objects.all_with_deleted()


@admin.register(ProjectSoilSettings)
class ProjectSoilSettingsAdmin(SafeDeleteAdmin):
    readonly_fields = ("deleted_at",)
    list_display = (
        highlight_deleted,
        "project",
        "depth_interval_preset",
        "deleted_at",
    )
    list_filter = (SafeDeleteAdminFilter, "depth_interval_preset")
    inlines = [ProjectDepthIntervalInline]
    search_fields = ["project__name"]


@admin.register(SoilData)
class SoilDataAdmin(SafeDeleteAdmin):
    @admin.display(ordering="site__name")
    def site_name(self, obj):
        return obj.site.name

    @admin.display(ordering="site__owner")
    def site_owner(self, obj):
        return obj.site.owner

    @admin.display(ordering="site__project__name")
    def project(self, obj):
        return obj.site.project.name if obj.site.project is not None else None

    readonly_fields = ("deleted_at",)
    list_display = [
        highlight_deleted,
        "site_name",
        "project",
        "site_owner",
        "depth_interval_preset",
        "deleted_at",
    ]
    list_filter = (SafeDeleteAdminFilter, "depth_interval_preset")
    search_fields = ["site__name", "site__project__name"]
    inlines = [
        DepthDependentSoilDataInline,
        SoilDataDepthIntervalInline,
    ]


@admin.register(SoilIdCache)
class SoilIdCacheAdmin(admin.ModelAdmin):
    list_display = ["id", "latitude", "longitude"]


@admin.register(SoilDataHistory)
class SoilDataHistoryAdmin(SafeDeleteAdmin):
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


@admin.register(SoilMetadata)
class SoilMetadataAdmin(SafeDeleteAdmin):
    @admin.display(ordering="site__name")
    def site_name(self, obj):
        return obj.site.name

    @admin.display(ordering="site__owner")
    def site_owner(self, obj):
        return obj.site.owner

    @admin.display(description="Selected Soil (derived from user ratings)")
    def selected_soil_display(self, obj):
        """Display the selected soil ID from user_ratings for backwards compatibility"""
        return obj.selected_soil_id

    def admin_warning(self, obj):
        return '^^ WARNING! ^^ \nUser ratings does not enforce proper formatting.\n Format like:\n{"Humic nitisols": "REJECTED", "Haplic nitisols": "SELECTED", "Eutric cambisols": "UNSURE"}'

    list_display = [
        highlight_deleted,
        "site_name",
        "site_owner",
        "selected_soil_display",
        "deleted_at",
    ]
    list_filter = (SafeDeleteAdminFilter,)
    search_fields = ["site__name", "site__owner__email"]
    readonly_fields = ["admin_warning", "selected_soil_display", "deleted_at"]
