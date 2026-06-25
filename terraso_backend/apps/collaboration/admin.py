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
from safedelete.admin import SafeDeleteAdmin, SafeDeleteAdminFilter, highlight_deleted

from .models import Membership, MembershipList


class MembershipInline(admin.TabularInline):
    model = Membership
    # Show soft-deleted memberships alongside active ones in the inline,
    # so the full historical state of a MembershipList is visible.
    fields = ("user", "pending_email", "user_role", "membership_status", "deleted_at")
    readonly_fields = ("deleted_at",)
    extra = 0

    def get_queryset(self, request):
        return Membership.objects.all_with_deleted()


@admin.register(MembershipList)
class MembershipListAdmin(SafeDeleteAdmin):
    @admin.display(ordering="project__name", description="Project")
    def project(self, obj):
        # Reverse OneToOne — only populated for ProjectMembershipLists.
        # Returns None for Group/Landscape membership lists.
        return getattr(obj, "project", None)

    list_display = (
        highlight_deleted,
        "project",
        "id",
        "membership_type",
        "enroll_method",
        "deleted_at",
        "created_at",
    )
    list_filter = (SafeDeleteAdminFilter, "membership_type", "enroll_method")
    inlines = [MembershipInline]
    search_fields = ["project__name", "id"]


@admin.register(Membership)
class MembershipAdmin(SafeDeleteAdmin):
    @admin.display(ordering="membership_list__project__name", description="Project")
    def project(self, obj):
        return getattr(obj.membership_list, "project", None)

    list_display = [
        highlight_deleted,
        "user",
        "pending_email",
        "project",
        "user_role",
        "membership_status",
        "deleted_at",
        "created_at",
    ]
    list_filter = (SafeDeleteAdminFilter, "user_role", "membership_status")
    search_fields = [
        "user__email",
        "pending_email",
        "membership_list__project__name",
    ]
    readonly_fields = ("deleted_at",)
