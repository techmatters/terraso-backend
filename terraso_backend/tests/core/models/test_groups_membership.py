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

from apps.collaboration.models import Membership as CollaborationMembership
from apps.core import group_collaboration_roles
from apps.core.models import Group, User

pytestmark = pytest.mark.django_db


def test_groups_membership_is_created_when_group_member_added():
    group = mixer.blend(Group, name="This is My Name", slug=None)
    users = mixer.cycle(3).blend(User)

    for user in users:
        group.membership_list.save_membership(
            user.email, group_collaboration_roles.ROLE_MEMBER, CollaborationMembership.APPROVED
        )

    assert group.membership_list.members.count() == 3
    assert CollaborationMembership.objects.count() == 3


def test_groups_membership_is_deleted_when_user_is_deleted():
    user = mixer.blend(User)
    group = mixer.blend(Group)

    group.membership_list.save_membership(
        user.email, group_collaboration_roles.ROLE_MEMBER, CollaborationMembership.APPROVED
    )

    membership = CollaborationMembership.objects.get(user=user, membership_list__group=group)

    assert membership

    user.delete()

    assert not User.objects.filter(id=user.id).exists()
    assert not CollaborationMembership.objects.filter(
        user=user, membership_list__group=group
    ).exists()
