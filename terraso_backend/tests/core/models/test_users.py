﻿# Copyright © 2021-2023 Technology Matters
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
from mixer.backend.django import mixer

from apps.core.models import Group, Landscape, LandscapeGroup, User

pytestmark = pytest.mark.django_db


def test_user_string_format_is_its_email():
    user_email = "test@example.com"
    user = mixer.blend(User, email=user_email)

    assert user_email == str(user)


def test_user_string_remove_spaces_from_name():
    user_first_name = "First Name "
    user_last_name = "Last Name "
    user = mixer.blend(User, first_name=user_first_name, last_name=user_last_name)

    assert user_first_name.strip() == user.first_name
    assert user_last_name.strip() == user.last_name


@pytest.mark.parametrize(
    "is_default_landscape_group, is_expected_to_be_manager",
    (
        (True, True),
        (False, False),
    ),
)
def test_user_is_landscape_manager(is_default_landscape_group, is_expected_to_be_manager):
    user = mixer.blend(User)
    group = mixer.blend(Group)
    landscape = mixer.blend(Landscape)
    mixer.blend(
        LandscapeGroup,
        landscape=landscape,
        group=group,
        is_default_landscape_group=is_default_landscape_group,
    )
    group.add_manager(user)

    assert user.is_landscape_manager(landscape.id) is is_expected_to_be_manager
