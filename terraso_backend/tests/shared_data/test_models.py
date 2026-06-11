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

from apps.collaboration.models import Membership as CollaborationMembership
from apps.core import group_collaboration_roles
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


def test_delete_user_with_shared_data_is_blocked(user, data_entry):
    """DataEntry.created_by is DO_NOTHING — under the soft-delete gate
    any user with DataEntries is refused. The previous DataEntry re-link
    branch in User.soft_delete_policy_action has been removed because
    it's unreachable on the success path. See
    backend/docs/user_soft_delete_plan.md, Settled decisions section."""
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError, match="undeletable data"):
        user.delete()
    user.refresh_from_db()
    assert user.deleted_at is None
    data_entry.refresh_from_db()
    assert data_entry.created_by == user


def test_data_entry_can_be_viewed_by_story_map_creator(user, story_map_data_entry, story_map):
    assert user.has_perm(DataEntry.get_perm("view"), obj=story_map_data_entry)


def test_data_entry_can_be_viewed_by_story_map_members(
    user, user_b, story_map_with_membership, data_entry
):
    data_entry.shared_resources.create(target=story_map_with_membership)
    assert user_b.has_perm(DataEntry.get_perm("view"), obj=data_entry)


def test_data_entry_cannot_be_viewed_by_non_story_map_members(user_b, story_map_data_entry):
    assert not user_b.has_perm(DataEntry.get_perm("view"), obj=story_map_data_entry)


def test_data_entry_can_be_deleted_by_story_map_creator(user, story_map_data_entry):
    assert user.has_perm(DataEntry.get_perm("delete"), obj=story_map_data_entry)


def test_visualization_config_can_be_viewed_by_story_map_creator(
    user, story_map_visualization_config
):
    assert user.has_perm(VisualizationConfig.get_perm("view"), obj=story_map_visualization_config)


def test_visualization_config_can_be_viewed_by_story_map_members(
    user, user_b, story_map_with_membership, visualization_config
):
    visualization_config.data_entry.shared_resources.create(target=story_map_with_membership)
    assert user_b.has_perm(VisualizationConfig.get_perm("view"), obj=visualization_config)


def test_visualization_config_can_be_deleted_by_story_map_creator(
    user, story_map_visualization_config
):
    assert user.has_perm(VisualizationConfig.get_perm("delete"), obj=story_map_visualization_config)
