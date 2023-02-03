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

from apps.core.models import Group, Membership, User

pytestmark = pytest.mark.django_db


def test_membership_is_created_when_group_member_added():
    group = mixer.blend(Group, name="This is My Name", slug=None)
    users = mixer.cycle(3).blend(User)

    group.members.add(*users)

    assert group.members.count() == 3
    assert Membership.objects.count() == 3


def test_membership_is_deleted_when_user_is_deleted():
    user = mixer.blend(User)
    group = mixer.blend(Group)

    group.members.add(user)

    membership = Membership.objects.get(user=user, group=group)

    assert membership

    user.delete()

    assert not User.objects.filter(id=user.id).exists()
    assert not Membership.objects.filter(user=user, group=group).exists()
