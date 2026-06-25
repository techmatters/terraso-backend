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


def test_groups_membership_blocks_user_deletion():
    """An APPROVED non-project Membership blocks user soft-deletion
    (Group/Landscape membership is undeletable web data; the membership
    has to be cleaned up manually before the user can be deleted)."""
    from django.core.exceptions import ValidationError

    user = mixer.blend(User)
    group = mixer.blend(Group)

    group.membership_list.save_membership(
        user.email, group_collaboration_roles.ROLE_MEMBER, CollaborationMembership.APPROVED
    )

    with pytest.raises(ValidationError, match="undeletable data"):
        user.delete()

    # User is still active; membership still in place.
    user.refresh_from_db()
    assert user.deleted_at is None
    assert CollaborationMembership.objects.filter(user=user, membership_list__group=group).exists()
