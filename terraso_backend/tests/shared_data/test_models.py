import pytest

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
    data_entry.groups.add(group)

    assert user_b.has_perm(DataEntry.get_perm("delete"), obj=data_entry)


def test_data_entry_cannot_be_deleted_by_non_creator_or_manager(user, user_b, data_entry_user_b):
    assert not user.has_perm(DataEntry.get_perm("delete"), obj=data_entry_user_b)


def test_data_entry_can_be_viewed_by_group_members(user, user_b, group, data_entry):
    group.members.add(user, user_b)
    data_entry.groups.add(group)

    assert user_b.has_perm(DataEntry.get_perm("view"), obj=data_entry)


def test_data_entry_cannot_be_viewed_by_non_group_members(user, user_b, group, data_entry):
    group.members.add(user)
    data_entry.groups.add(group)

    assert not user_b.has_perm(DataEntry.get_perm("view"), obj=data_entry)


def test_visualization_config_can_be_updated_by_its_creator(user, visualization_config):
    assert user.has_perm(VisualizationConfig.get_perm("change"), obj=visualization_config)


def test_visualization_config_cannot_be_updated_by_non_creator(user, visualization_config_b):
    assert not user.has_perm(VisualizationConfig.get_perm("change"), obj=visualization_config_b)


def test_visualization_config_cannot_be_updated_by_group_manager(
    user_b, group, visualization_config
):
    group.add_manager(user_b)
    visualization_config.data_entry.groups.add(group)

    assert not user_b.has_perm(VisualizationConfig.get_perm("change"), obj=visualization_config)


def test_visualization_config_can_be_deleted_by_its_creator(user, visualization_config):
    assert user.has_perm(VisualizationConfig.get_perm("delete"), obj=visualization_config)


def test_visualization_config_cannot_be_deleted_by_non_creator(user, visualization_config_b):
    assert not user.has_perm(VisualizationConfig.get_perm("delete"), obj=visualization_config_b)


def test_visualization_config_can_be_deleted_by_group_manager(user_b, group, visualization_config):
    group.add_manager(user_b)
    visualization_config.data_entry.groups.add(group)

    assert user_b.has_perm(VisualizationConfig.get_perm("delete"), obj=visualization_config)


def test_visualization_config_can_be_viewed_by_group_members(
    user, user_b, group, visualization_config
):
    group.members.add(user, user_b)
    visualization_config.data_entry.groups.add(group)

    assert user_b.has_perm(VisualizationConfig.get_perm("view"), obj=visualization_config)
    assert user.has_perm(VisualizationConfig.get_perm("view"), obj=visualization_config)


def test_visualization_config_cannot_be_viewed_by_non_group_members(
    user, user_b, group, visualization_config
):
    group.members.add(user)
    visualization_config.data_entry.groups.add(group)

    assert not user_b.has_perm(VisualizationConfig.get_perm("view"), obj=visualization_config)
    assert user.has_perm(VisualizationConfig.get_perm("view"), obj=visualization_config)
