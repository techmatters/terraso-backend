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
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from mixer.backend.django import mixer

from apps.collaboration.models import Membership as CollaborationMembership
from apps.core import group_collaboration_roles, landscape_collaboration_roles
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


def test_user_is_landscape_manager():
    user = mixer.blend(User)
    landscape = mixer.blend(Landscape)
    landscape.membership_list.save_membership(
        user.email, landscape_collaboration_roles.ROLE_MANAGER, CollaborationMembership.APPROVED
    )

    assert user.is_landscape_manager(landscape.id) is True


def test_user_is_landscape_manager_returns_false_for_none_id():
    user = mixer.blend(User)
    group = mixer.blend(Group)
    group.membership_list.save_membership(
        user.email, group_collaboration_roles.ROLE_MANAGER, CollaborationMembership.APPROVED
    )

    assert user.is_landscape_manager(None) is False


def test_user_is_group_manager_returns_false_for_none_id():
    user = mixer.blend(User)
    landscape = mixer.blend(Landscape)
    landscape.membership_list.save_membership(
        user.email, landscape_collaboration_roles.ROLE_MANAGER, CollaborationMembership.APPROVED
    )

    assert user.is_group_manager(None) is False


def test_user_does_not_get_global_group_permissions_from_manager_membership():
    user = mixer.blend(User, is_staff=True)
    group = mixer.blend(Group)
    landscape = mixer.blend(Landscape)

    group.membership_list.save_membership(
        user.email, group_collaboration_roles.ROLE_MANAGER, CollaborationMembership.APPROVED
    )
    landscape.membership_list.save_membership(
        user.email, landscape_collaboration_roles.ROLE_MANAGER, CollaborationMembership.APPROVED
    )

    group_content_type = ContentType.objects.get_for_model(Group)
    landscape_content_type = ContentType.objects.get_for_model(Landscape)
    landscape_group_content_type = ContentType.objects.get_for_model(LandscapeGroup)

    user.user_permissions.add(
        Permission.objects.get(codename="view_group", content_type=group_content_type),
        Permission.objects.get(codename="view_landscape", content_type=landscape_content_type),
        Permission.objects.get(
            codename="view_landscapegroup", content_type=landscape_group_content_type
        ),
    )

    assert user.has_perm(Group.get_perm("change"), obj=group.id)
    assert user.has_perm(Group.get_perm("delete"), obj=group.id)
    assert user.has_perm(Landscape.get_perm("change"), obj=landscape.id)
    assert user.has_perm(Landscape.get_perm("delete"), obj=landscape.id)
    assert user.has_perm(LandscapeGroup.get_perm("add"), obj=landscape.id)

    assert not user.has_perm(Group.get_perm("change"))
    assert not user.has_perm(Group.get_perm("delete"))
    assert not user.has_perm(Landscape.get_perm("change"))
    assert not user.has_perm(Landscape.get_perm("delete"))
    assert not user.has_perm(LandscapeGroup.get_perm("add"))


# --- undelete (account restoration) ---


def test_user_undelete_restores_soft_deleted_account():
    """SafeDeleteAdmin's "Undelete" action (and any other caller) should
    restore a soft-deleted user when their email isn't taken."""
    user = mixer.blend(User, email="restorable@example.test")
    user.delete()  # soft-delete via SafeDelete

    user.refresh_from_db()
    assert user.deleted_at is not None
    assert not User.objects.filter(pk=user.pk).exists()  # default mgr hides

    user.undelete()
    user.refresh_from_db()
    assert user.deleted_at is None
    assert User.objects.filter(pk=user.pk).exists()


def test_user_undelete_refuses_when_email_is_taken_by_active_user():
    """The conditional `unique_active_email` constraint lets a soft-deleted
    user's email be re-registered while they're in the grace window.
    Undelete must refuse rather than let the unique constraint blow up
    with an IntegrityError mid-save."""
    from django.core.exceptions import ValidationError

    original = mixer.blend(User, email="collision@example.test")
    original.delete()  # soft-delete

    # Someone else signs up with the same email — allowed by the
    # conditional unique constraint.
    new_user = mixer.blend(User, email="collision@example.test")
    assert new_user.pk != original.pk
    assert User.objects.filter(email="collision@example.test").count() == 1

    with pytest.raises(ValidationError, match="another active user"):
        original.undelete()

    # Original stays soft-deleted; the new user is undisturbed.
    original.refresh_from_db()
    assert original.deleted_at is not None
    assert User.objects.filter(pk=new_user.pk, deleted_at__isnull=True).exists()


def test_user_undelete_allowed_when_no_email_collision():
    """Sanity: a different active email doesn't block undelete."""
    user = mixer.blend(User, email="alone@example.test")
    user.delete()
    # Different email exists, but doesn't collide.
    mixer.blend(User, email="unrelated@example.test")

    user.undelete()
    user.refresh_from_db()
    assert user.deleted_at is None
