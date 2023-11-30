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
from django.db import models

from apps.collaboration.models import Membership as CollaborationMembership
from apps.core import group_collaboration_roles
from apps.core.models import User
from apps.shared_data.models import DataEntry, VisualizationConfig

pytestmark = pytest.mark.django_db


def test_data_entry_string_format_is_its_name(data_entry):
    assert data_entry.name == str(data_entry)


def test_data_entry_get_s3_object_name(user, data_entry, data_entry_filename):
    assert data_entry.s3_object_name == f"{user.id}/{data_entry_filename}"


def test_data_entry_get_signed_url(settings, data_entry):
    # Set custom domain to make sure the signed URLs works properly with it set
    settings.AWS_S3_CUSTOM_DOMAIN = "testing.terraso.org"

    assert data_entry.s3_object_name in data_entry.signed_url
    assert "X-Amz-Expires" in data_entry.signed_url


def test_data_entry_can_be_updated_by_its_creator(user, data_entry):
    assert user.has_perm(DataEntry.get_perm("change"), obj=data_entry)


def test_data_entry_cannot_be_updated_by_non_creator(user, user_b, data_entry_user_b):
    assert not user.has_perm(DataEntry.get_perm("change"), obj=data_entry_user_b)


def test_data_entry_can_be_deleted_by_its_creator(user, data_entry):
    assert user.has_perm(DataEntry.get_perm("delete"), obj=data_entry)


def test_data_entry_can_be_deleted_by_group_manager(user_b, group, data_entry):
    group.add_manager(user_b)
    data_entry.shared_resources.create(target=group)

    assert user_b.has_perm(DataEntry.get_perm("delete"), obj=data_entry)


def test_data_entry_cannot_be_deleted_by_non_creator_or_manager(user, user_b, data_entry_user_b):
    assert not user.has_perm(DataEntry.get_perm("delete"), obj=data_entry_user_b)


def test_data_entry_can_be_viewed_by_group_members(user, user_b, group, data_entry):
    for user in [user, user_b]:
        group.membership_list.save_membership(
            user.email, group_collaboration_roles.ROLE_MEMBER, CollaborationMembership.APPROVED
        )
    data_entry.shared_resources.create(target=group)

    assert user_b.has_perm(DataEntry.get_perm("view"), obj=data_entry)


def test_data_entry_cannot_be_viewed_by_non_group_members(user, user_b, group, data_entry):
    group.membership_list.save_membership(
        user.email, group_collaboration_roles.ROLE_MEMBER, CollaborationMembership.APPROVED
    )
    data_entry.shared_resources.create(target=group)

    assert not user_b.has_perm(DataEntry.get_perm("view"), obj=data_entry)


def test_visualization_config_can_be_updated_by_its_creator(user, visualization_config):
    assert user.has_perm(VisualizationConfig.get_perm("change"), obj=visualization_config)


def test_visualization_config_cannot_be_updated_by_non_creator(user, visualization_config_b):
    assert not user.has_perm(VisualizationConfig.get_perm("change"), obj=visualization_config_b)


def test_visualization_config_cannot_be_updated_by_group_manager(
    user_b, group, visualization_config
):
    group.add_manager(user_b)
    visualization_config.data_entry.shared_resources.create(target=group)

    assert not user_b.has_perm(VisualizationConfig.get_perm("change"), obj=visualization_config)


def test_visualization_config_can_be_deleted_by_its_creator(user, visualization_config):
    assert user.has_perm(VisualizationConfig.get_perm("delete"), obj=visualization_config)


def test_visualization_config_cannot_be_deleted_by_non_creator(user, visualization_config_b):
    assert not user.has_perm(VisualizationConfig.get_perm("delete"), obj=visualization_config_b)


def test_visualization_config_can_be_deleted_by_group_manager(user_b, group, visualization_config):
    group.add_manager(user_b)
    visualization_config.data_entry.shared_resources.create(target=group)

    assert user_b.has_perm(VisualizationConfig.get_perm("delete"), obj=visualization_config)


def test_visualization_config_can_be_viewed_by_group_members(
    user, user_b, group, visualization_config
):
    for user in [user, user_b]:
        group.membership_list.save_membership(
            user.email, group_collaboration_roles.ROLE_MEMBER, CollaborationMembership.APPROVED
        )
    visualization_config.data_entry.shared_resources.create(target=group)

    assert user_b.has_perm(VisualizationConfig.get_perm("view"), obj=visualization_config)
    assert user.has_perm(VisualizationConfig.get_perm("view"), obj=visualization_config)


def test_visualization_config_cannot_be_viewed_by_non_group_members(
    user, user_b, group, visualization_config
):
    group.membership_list.save_membership(
        user.email, group_collaboration_roles.ROLE_MEMBER, CollaborationMembership.APPROVED
    )
    visualization_config.data_entry.shared_resources.create(target=group)

    assert not user_b.has_perm(VisualizationConfig.get_perm("view"), obj=visualization_config)
    assert user.has_perm(VisualizationConfig.get_perm("view"), obj=visualization_config)


def test_delete_user_with_shared_data(user, data_entry):
    try:
        user.delete()
    except models.deletion.ProtectedError as e:
        assert False, f"Deleting a user should not raise an exception. {e}"
    assert not User.objects.filter(id=user.id).exists(), "User should be soft-deleted"
    assert DataEntry.objects.filter(id=data_entry.id).exists(), "Data entry should not be deleted"
    data_entry.refresh_from_db()
    assert data_entry.created_by == user, "Data entry should still link to user"
