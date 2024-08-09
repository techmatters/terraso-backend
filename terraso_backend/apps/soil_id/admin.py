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

from apps.soil_id.models import (
    DepthDependentSoilData,
    ProjectDepthInterval,
    ProjectSoilSettings,
    SoilData,
    SoilDataDepthInterval,
)


class DepthDependentSoilDataInline(admin.TabularInline):
    model = DepthDependentSoilData


class SoilDataDepthIntervalInline(admin.TabularInline):
    model = SoilDataDepthInterval


class ProjectDepthIntervalInline(admin.TabularInline):
    model = ProjectDepthInterval


@admin.register(ProjectSoilSettings)
class ProjectSoilSettingsAdmin(admin.ModelAdmin):
    list_display = ("project", "depth_interval_preset")
    inlines = [
        ProjectDepthIntervalInline,
    ]
    search_fields = ["project__name"]


@admin.register(SoilData)
class SoilDataAdmin(admin.ModelAdmin):
    @admin.display(ordering="site__name")
    def site_name(self, obj):
        return obj.site.name

    @admin.display(ordering="site__owner")
    def site_owner(self, obj):
        return obj.site.owner

    @admin.display(ordering="site__project__name")
    def project(self, obj):
        return obj.site.project.name if obj.site.project is not None else None

    list_display = ["site_name", "project", "site_owner", "depth_interval_preset"]
    search_fields = ["site__name", "site__project__name"]
    inlines = [
        DepthDependentSoilDataInline,
        SoilDataDepthIntervalInline,
    ]
