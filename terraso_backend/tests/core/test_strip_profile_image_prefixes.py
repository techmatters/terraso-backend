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

import pytest
from django.core.management import call_command
from mixer.backend.django import mixer

from apps.core.management.commands.strip_profile_image_prefixes import key_from_value
from apps.core.models import User
from apps.core.models.landscapes import Landscape


def test_key_from_cdn_url():
    assert (
        key_from_value("abc", "https://images.terraso.org/abc/profile-image_2")
        == "abc/profile-image_2"
    )


def test_key_from_path_style_url_strips_bucket():
    assert (
        key_from_value("abc", "http://host:9000/terraso-local-profile-images/abc/profile-image")
        == "abc/profile-image"
    )


def test_key_already_a_key_is_unchanged():
    assert key_from_value("abc", "abc/profile-image_2") == "abc/profile-image_2"


def test_key_empty_is_unchanged():
    assert key_from_value("abc", "") == ""


def test_key_unexpected_shape_returns_none():
    # No `<id>/` anchor in the path -> can't derive safely.
    assert key_from_value("abc", "https://host/some/other/path.jpg") is None


@pytest.mark.django_db
def test_command_rewrites_user_and_landscape_to_keys():
    user = mixer.blend(User)
    user.profile_image = f"https://images.terraso.org/{user.id}/profile-image_3"
    user.save()

    landscape = mixer.blend(Landscape)
    landscape.profile_image = (
        f"http://host:9000/terraso-local-profile-images/{landscape.id}/profile-image"
    )
    landscape.save()

    call_command("strip_profile_image_prefixes")

    user.refresh_from_db()
    landscape.refresh_from_db()
    assert user.profile_image == f"{user.id}/profile-image_3"
    assert landscape.profile_image == f"{landscape.id}/profile-image"

    # Idempotent: a second run leaves the bare keys untouched.
    call_command("strip_profile_image_prefixes")
    user.refresh_from_db()
    assert user.profile_image == f"{user.id}/profile-image_3"
