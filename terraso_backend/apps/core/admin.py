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

from django.contrib import admin

from .models import (
    Group,
    Landscape,
    LandscapeDevelopmentStrategy,
    LandscapeGroup,
    Membership,
    TaxonomyTerm,
    User,
)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "website", "created_at")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        landscape_group_ids = [
            values[0]
            for values in LandscapeGroup.objects.filter(
                is_default_landscape_group=True
            ).values_list("group__id")
        ]
        return qs.exclude(id__in=landscape_group_ids)


@admin.register(Landscape)
class LandscapeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "location", "website", "created_at")


@admin.register(LandscapeGroup)
class LandscapeGroupAdmin(admin.ModelAdmin):
    list_display = ("landscape", "group")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "group", "user_role", "membership_status", "created_at")


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "first_name", "last_name", "created_at", "is_staff")


@admin.register(TaxonomyTerm)
class TaxonomyTermAdmin(admin.ModelAdmin):
    list_display = ("value_original", "type", "value_en", "value_es")


@admin.register(LandscapeDevelopmentStrategy)
class LandscapeDevelopmentStrategyAdmin(admin.ModelAdmin):
    list_display = ("id", "landscape")
