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
from mixer.backend.django import mixer

from apps.auth.services import JWTService
from apps.collaboration.models import Membership as CollaborationMembership
from apps.core import landscape_collaboration_roles
from apps.core.models import Landscape, User


@pytest.fixture
def access_token(user):
    return JWTService().create_access_token(user)


@pytest.fixture
def user():
    return mixer.blend(User)


@pytest.fixture
def landscape(user):
    landscape = mixer.blend(Landscape)
    landscape.membership_list.save_membership(
        user.email,
        landscape_collaboration_roles.ROLE_MANAGER,
        CollaborationMembership.APPROVED,
    )
    return landscape
