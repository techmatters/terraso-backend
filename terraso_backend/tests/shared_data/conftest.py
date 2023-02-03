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

import pytest
from django.conf import settings
from mixer.backend.django import mixer

from apps.core.models import Group, User
from apps.shared_data.models import DataEntry, VisualizationConfig


@pytest.fixture
def user():
    return mixer.blend(User)


@pytest.fixture
def user_b():
    return mixer.blend(User)


@pytest.fixture
def group():
    return mixer.blend(Group)


@pytest.fixture
def data_entry_filename():
    return "test_data.csv"


@pytest.fixture
def data_entry(user, data_entry_filename):
    return mixer.blend(
        DataEntry,
        size=1,
        url=f"{settings.DATA_ENTRY_FILE_BASE_URL}/{user.id}/{data_entry_filename}",
        created_by=user,
    )


@pytest.fixture
def data_entry_user_b(user_b, data_entry_filename):
    return mixer.blend(
        DataEntry,
        size=1,
        url=f"{settings.DATA_ENTRY_FILE_BASE_URL}/{user_b.id}/{data_entry_filename}",
        created_by=user_b,
    )


@pytest.fixture
def visualization_config(user, data_entry):
    return mixer.blend(
        VisualizationConfig,
        size=1,
        data_entry=data_entry,
        created_by=user,
    )


@pytest.fixture
def visualization_config_b(user_b, data_entry):
    return mixer.blend(
        VisualizationConfig,
        size=1,
        data_entry=data_entry,
        created_by=user_b,
    )
