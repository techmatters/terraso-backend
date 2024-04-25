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

import pytest
from mixer.backend.django import mixer

from apps.core.models.users import User

pytestmark = pytest.mark.django_db


def test_is_sole_manager_one_manager(project, project_manager):
    assert project.is_sole_manager(project_manager) is True


def test_is_sole_manager_no_membership(project):
    user = mixer.blend(User)
    assert project.is_sole_manager(user) is False


def test_is_sole_manager_not_manager(project):
    user = mixer.blend(User)
    project.add_contributor(user)
    assert project.is_sole_manager(user) is False


def test_is_sole_manager_multiple_managers(project, project_manager):
    user = mixer.blend(User)
    project.add_manager(user)
    assert project.is_sole_manager(user) is False
    assert project.is_sole_manager(project_manager) is False
