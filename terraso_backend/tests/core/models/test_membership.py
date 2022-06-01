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
