import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
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


def test_group_string_remove_spaces_from_name():
    group_name = "Terraso Group Name "
    group = mixer.blend(Group, name=group_name)

    assert group_name.strip() == str(group)


def test_group_string_remove_spaces_from_description():
    group_name = "Terraso Group Name"
    group_description = "Terraso Group Description "
    group = mixer.blend(Group, name=group_name)
    group.description = group_description
    group.save()

    assert group_description.strip() == group.description


def test_group_disallowed_name():
    group_name = "New"
    group = mixer.blend(Group, name=group_name)

    with pytest.raises(ValidationError, match="New is not allowed as a name"):
        group.full_clean()


def test_group_additional_disallowed_name():
    group_name = "Foobar"
    settings.DISALLOWED_NAMES_LIST = ["new", "foobar"]
    group = mixer.blend(Group, name=group_name)

    with pytest.raises(ValidationError, match="Foobar is not allowed as a name"):
        group.full_clean()


def test_group_slug_is_updatable():
    group = mixer.blend(Group, name="This is My Name", slug=None)
    group.name = "New name"
    group.save()

    assert group.slug == "new-name"
    assert group.name == "New name"


def test_group_add_manager():
    group = mixer.blend(Group)
    user = mixer.blend(User)

    group.add_manager(user)

    assert Membership.objects.filter(
        user=user, group=group, user_role=Membership.ROLE_MANAGER
    ).exists()


def test_group_add_manager_updates_previous_membership():
    group = mixer.blend(Group)
    user = mixer.blend(User)
    old_membership = mixer.blend(
        Membership, user=user, group=group, user_role=Membership.ROLE_MEMBER
    )

    group.add_manager(user)

    updated_membership = Membership.objects.get(
        user=user, group=group, user_role=Membership.ROLE_MANAGER
    )

    assert old_membership.id == updated_membership.id
    assert updated_membership.user_role == Membership.ROLE_MANAGER


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


def test_group_creator_becomes_manager():
    user = mixer.blend(User)
    group = mixer.blend(Group, created_by=user)

    manager_membership = Membership.objects.get(group=group, user=user)

    assert manager_membership.user_role == Membership.ROLE_MANAGER
