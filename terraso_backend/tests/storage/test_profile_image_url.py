# Copyright © 2026 Technology Matters
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

from django.test import override_settings

from apps.storage.services import build_profile_image_url


@override_settings(PROFILE_IMAGES_BASE_URL="https://images.example.org")
def test_build_prepends_current_base_url_to_key():
    assert (
        build_profile_image_url("abc/profile-image_2")
        == "https://images.example.org/abc/profile-image_2"
    )


def test_build_empty_stays_empty():
    assert build_profile_image_url("") == ""
    assert build_profile_image_url(None) == ""


@override_settings(PROFILE_IMAGES_BASE_URL="https://images.example.org")
def test_build_passes_through_legacy_full_url():
    # TEMPORARY transition behavior: rows that still hold a full URL are returned
    # unchanged rather than double-prefixed. Remove with the passthrough branch.
    assert (
        build_profile_image_url("https://old.cdn/abc/profile-image")
        == "https://old.cdn/abc/profile-image"
    )
    assert (
        build_profile_image_url("http://old.cdn/abc/profile-image")
        == "http://old.cdn/abc/profile-image"
    )
