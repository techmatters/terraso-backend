# Copyright © 2023 Technology Matters
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

from .models import Membership, MembershipList


class MembershipInline(admin.TabularInline):
    model = Membership


@admin.register(MembershipList)
class MembershipListAdmin(admin.ModelAdmin):
    list_display = ("project", "id", "created_at")
    inlines = [MembershipInline]
    search_fields = ["project__name"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    @admin.display(ordering="membership_list__project")
    def project(self, obj):
        return obj.membership_list.project

    list_display = [
        "user",
        "project",
        "user_role",
        "membership_status",
        "membership_list",
        "created_at",
    ]
    search_fields = ["user__email", "membership_list__project__name"]
