import pytest
from mixer.backend.django import mixer

from apps.core.models.groups import Group, GroupAssociation, Membership
from apps.core.models.users import User

pytestmark = pytest.mark.django_db


def test_group_string_format_is_its_name():
    group_name = "Terraso Group Name"
    group = mixer.blend(Group, name=group_name)

    assert group_name == str(group)


def test_group_is_slugifiable_by_name():
    group = mixer.blend(Group, name="This is My Name", slug=None)

    assert group.slug == "this-is-my-name"


def test_group_slug_is_updatable():
    group = mixer.blend(Group, name="This is My Name", slug=None)
    group.name = "New name"
    group.save()

    assert group.slug == "new-name"
    assert group.name == "New name"


def test_group_can_have_group_associations():
    group = mixer.blend(Group)
    subgroup = mixer.blend(Group)

    group.group_associations.add(subgroup)

    assert group.group_associations.count() == 1


def test_group_associations_creation_explicitly():
    group = mixer.blend(Group)
    subgroup = mixer.blend(Group)

    GroupAssociation.objects.create(parent_group=group, child_group=subgroup)

    assert group.associations_as_parent.count() == 1
    assert subgroup.associations_as_child.count() == 1


def test_group_associations_are_asymmetrical():
    # Asymmetrical means that if a Group A is parent of Group B, it
    # doesn't mean that Group B is also parent of Group A
    group = mixer.blend(Group)
    subgroup = mixer.blend(Group)

    group.group_associations.add(subgroup)

    assert subgroup.associations_as_parent.count() == 0
    assert group.associations_as_child.count() == 0


def test_membership_is_created_when_group_member_added():
    group = mixer.blend(Group, name="This is My Name", slug=None)
    users = mixer.cycle(3).blend(User)

    group.members.add(*users)

    assert group.members.count() == 3
    assert Membership.objects.count() == 3
