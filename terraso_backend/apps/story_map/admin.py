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

from urllib.parse import unquote, urlparse

from django import forms
from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html
from safedelete.admin import SafeDeleteAdmin, SafeDeleteAdminFilter, highlight_deleted

from .models import StoryMap


def _extract_story_map_lookup(search_term):
    normalized_search_term = unquote(search_term.strip())
    if not normalized_search_term:
        return None

    parsed_url = urlparse(normalized_search_term)
    candidate_path = (
        parsed_url.path if parsed_url.scheme or parsed_url.netloc else normalized_search_term
    )
    path_segments = [segment for segment in candidate_path.split("/") if segment]

    if "story-maps" in path_segments:
        story_maps_index = path_segments.index("story-maps")
        path_segments = path_segments[story_maps_index + 1 :]

    if not path_segments:
        return None

    story_map_id = path_segments[0]
    slug = path_segments[1] if len(path_segments) > 1 else None
    return story_map_id, slug


def _get_story_map_web_client_url(story_map, *, embed=False):
    if not settings.WEB_CLIENT_URL or not story_map.story_map_id or not story_map.slug:
        return None

    parsed_web_client_url = urlparse(settings.WEB_CLIENT_URL)
    if not parsed_web_client_url.scheme or not parsed_web_client_url.netloc:
        return None

    story_map_url = f"{settings.WEB_CLIENT_URL.rstrip('/')}/tools/story-maps/{story_map.story_map_id}/{story_map.slug}"
    if embed:
        return f"{story_map_url}/embed"

    return story_map_url


class CustomStoryMapForm(forms.ModelForm):
    class Meta:
        model = StoryMap
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        membership_list_field = self.fields.get("membership_list")
        if membership_list_field is not None:
            membership_list_field.required = False


@admin.register(StoryMap)
class StoryMapAdmin(SafeDeleteAdmin):
    config_readonly_fields = ("configuration", "published_configuration")
    readonly_fields = ("web_client_preview",)
    list_display = (
        highlight_deleted,
        "story_map_name",
        "owner",
        "is_published",
        "featured",
        "published_at",
    )
    list_filter = ("is_published", "featured", SafeDeleteAdminFilter)
    list_select_related = ("created_by",)
    search_fields = (
        "title",
        "story_map_id",
        "slug",
        "created_by__email",
        "created_by__first_name",
        "created_by__last_name",
    )
    raw_id_fields = ("membership_list",)
    form = CustomStoryMapForm

    @admin.display(description="Story map name", ordering="title")
    def story_map_name(self, obj):
        return obj.title

    @admin.display(description="Owner", ordering="created_by__email")
    def owner(self, obj):
        return obj.created_by.email if obj.created_by else "-"

    @admin.display(description="Published Story Map Preview")
    def web_client_preview(self, obj):
        if obj is None or not obj.is_published:
            return "-"

        story_map_url = _get_story_map_web_client_url(obj)
        embed_url = _get_story_map_web_client_url(obj, embed=True)
        if not story_map_url or not embed_url:
            return "Preview unavailable. Set WEB_CLIENT_* config to enable it."

        return format_html(
            "<div>"
            '<p><a href="{story_map_url}" target="_blank" rel="noopener noreferrer">'
            "Open published story map"
            "</a></p>"
            '<iframe src="{embed_url}" title="Terraso Story Map" width="750" height="500" '
            'style="border: 1px solid #d0d7de;"></iframe>'
            "</div>",
            story_map_url=story_map_url,
            embed_url=embed_url,
        )

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if obj is None or not obj.is_published:
            return [field for field in fields if field != "web_client_preview"]

        return fields

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if request.user.is_superuser:
            return readonly_fields

        return readonly_fields + list(self.config_readonly_fields)

    def get_search_results(self, request, queryset, search_term):
        filtered_queryset = queryset
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        story_map_lookup = _extract_story_map_lookup(search_term)
        if not story_map_lookup:
            return queryset, use_distinct

        story_map_id, slug = story_map_lookup
        url_queryset = filtered_queryset.filter(story_map_id=story_map_id)
        if slug:
            url_queryset = url_queryset.filter(slug=slug)

        return queryset | url_queryset, True
