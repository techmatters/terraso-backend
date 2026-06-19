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

from django import forms
from django.contrib import admin
from safedelete.admin import SafeDeleteAdmin, SafeDeleteAdminFilter, highlight_deleted

from .models import StoryMap


class CustomStoryMapForm(forms.ModelForm):
    class Meta:
        model = StoryMap
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["membership_list"].required = False


@admin.register(StoryMap)
class StoryMapAdmin(SafeDeleteAdmin):
    # SafeDeleteAdmin gives:
    #   - Queryset that includes soft-deleted rows in the list view.
    #   - "highlight_deleted" indicator in list_display.
    #   - Active / Deleted / All filter in the sidebar.
    #   - "Undelete selected" bulk action.
    list_display = (highlight_deleted, "created_by", "deleted_at", "created_at")
    list_filter = (SafeDeleteAdminFilter,)
    search_fields = ("title", "created_by__email")
    raw_id_fields = ("membership_list",)
    form = CustomStoryMapForm
