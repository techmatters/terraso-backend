import uuid

import pytest
from mixer.backend.django import mixer

from apps.core.models import Group, LandscapeGroup

pytestmark = pytest.mark.django_db


def test_landscape_groups_add_by_landscape_manager(
    settings, client_query, managed_landscapes, groups
):
    landscape = managed_landscapes[0]
    group = groups[0]
    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

    response = client_query(
        """
        mutation addLandscapeGroup($input: LandscapeGroupAddMutationInput!){
          addLandscapeGroup(input: $input) {
            landscapeGroup {
              id
              landscape {
                name
              }
              group {
                name
              }
              isDefaultLandscapeGroup
            }
          }
        }
        """,
        variables={
            "input": {
                "landscapeSlug": landscape.slug,
                "groupSlug": group.slug,
            }
        },
    )
    landscape_group = response.json()["data"]["addLandscapeGroup"]["landscapeGroup"]

    assert landscape_group["id"]
    assert landscape_group["landscape"]["name"] == landscape.name
    assert landscape_group["group"]["name"] == group.name
    assert not landscape_group["isDefaultLandscapeGroup"]


def test_landscape_groups_add_by_non_landscape_manager_not_allowed(
    settings, client_query, landscapes, groups
):
    landscape = landscapes[0]
    group = groups[0]

    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

    response = client_query(
        """
        mutation addLandscapeGroup($input: LandscapeGroupAddMutationInput!){
          addLandscapeGroup(input: $input) {
            landscapeGroup {
              id
              landscape {
                name
              }
              group {
                name
              }
              isDefaultLandscapeGroup
            }
          }
        }
        """,
        variables={
            "input": {
                "landscapeSlug": landscape.slug,
                "groupSlug": group.slug,
            }
        },
    )
    response = response.json()

    assert "errors" in response
    assert "no permission" in response["errors"][0]["message"]


def test_landscape_groups_add_duplicated(settings, client_query, users, landscape_groups):
    user = users[0]
    landscape = landscape_groups[0].landscape
    group = landscape_groups[0].group
    group.add_manager(user)

    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

    response = client_query(
        """
        mutation addLandscapeGroup($input: LandscapeGroupAddMutationInput!){
          addLandscapeGroup(input: $input) {
            landscapeGroup {
              id
              landscape {
                name
              }
              group {
                name
              }
              isDefaultLandscapeGroup
            }
          }
        }
        """,
        variables={
            "input": {
                "landscapeSlug": landscape.slug,
                "groupSlug": group.slug,
            }
        },
    )
    error_result = response.json()["errors"][0]

    assert "duplicate key" in error_result["message"]


def test_landscape_groups_add_landscape_not_found(settings, client_query, groups):
    group = groups[0]
    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

    response = client_query(
        """
        mutation addLandscapeGroup($input: LandscapeGroupAddMutationInput!){
          addLandscapeGroup(input: $input) {
            landscapeGroup {
              id
              landscape {
                name
              }
              group {
                name
              }
              isDefaultLandscapeGroup
            }
          }
        }
        """,
        variables={
            "input": {
                "landscapeSlug": "non-existing-landscape",
                "groupSlug": group.slug,
            }
        },
    )
    response = response.json()

    assert "errors" in response
    assert "Landscape not found" in response["errors"][0]["message"]


def test_landscape_groups_add_group_not_found(settings, client_query, managed_landscapes):
    landscape = managed_landscapes[0]
    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

    response = client_query(
        """
        mutation addLandscapeGroup($input: LandscapeGroupAddMutationInput!){
          addLandscapeGroup(input: $input) {
            landscapeGroup {
              id
              landscape {
                name
              }
              group {
                name
              }
              isDefaultLandscapeGroup
            }
          }
        }
        """,
        variables={
            "input": {
                "landscapeSlug": landscape.slug,
                "groupSlug": "non-existing-group",
            }
        },
    )
    response = response.json()

    assert "errors" in response
    assert "Group not found" in response["errors"][0]["message"]


def test_landscape_groups_delete_by_group_manager(settings, client_query, users, landscape_groups):
    user = users[0]
    _, old_landscape_group = landscape_groups
    old_landscape_group.group.add_manager(user)

    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

    response = client_query(
        """
        mutation deleteLandscapeGroup($input: LandscapeGroupDeleteMutationInput!){
          deleteLandscapeGroup(input: $input) {
            landscapeGroup {
              landscape { slug }
              group { slug }
            }
          }
        }
        """,
        variables={"input": {"id": str(old_landscape_group.id)}},
    )
    landscape_group = response.json()["data"]["deleteLandscapeGroup"]["landscapeGroup"]

    assert not LandscapeGroup.objects.filter(
        landscape__slug=landscape_group["landscape"]["slug"],
        group__slug=landscape_group["group"]["slug"],
    )


def test_landscape_groups_delete_by_landscape_manager(
    settings, client_query, users, managed_landscapes
):
    landscape = managed_landscapes[0]
    group = mixer.blend(Group)
    old_landscape_group = mixer.blend(LandscapeGroup, landscape=landscape, group=group)

    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

    response = client_query(
        """
        mutation deleteLandscapeGroup($input: LandscapeGroupDeleteMutationInput!){
          deleteLandscapeGroup(input: $input) {
            landscapeGroup {
              landscape { slug }
              group { slug }
            }
          }
        }
        """,
        variables={"input": {"id": str(old_landscape_group.id)}},
    )
    landscape_group = response.json()["data"]["deleteLandscapeGroup"]["landscapeGroup"]

    assert not LandscapeGroup.objects.filter(
        landscape__slug=landscape_group["landscape"]["slug"],
        group__slug=landscape_group["group"]["slug"],
    )


def test_landscape_groups_delete_by_non_managers_not_allowed(
    settings, client_query, users, landscape_groups
):
    _, old_landscape_group = landscape_groups

    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

    response = client_query(
        """
        mutation deleteLandscapeGroup($input: LandscapeGroupDeleteMutationInput!){
          deleteLandscapeGroup(input: $input) {
            landscapeGroup {
              landscape { slug }
              group { slug }
            }
          }
        }
        """,
        variables={"input": {"id": str(old_landscape_group.id)}},
    )
    response = response.json()

    assert "errors" in response
    assert "no permission" in response["errors"][0]["message"]


def test_landscape_groups_delete_not_found(settings, client_query, users):
    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

    response = client_query(
        """
        mutation deleteLandscapeGroup($input: LandscapeGroupDeleteMutationInput!){
          deleteLandscapeGroup(input: $input) {
            landscapeGroup {
              landscape { slug }
              group { slug }
            }
          }
        }
        """,
        variables={"input": {"id": str(uuid.uuid4())}},
    )
    response = response.json()

    assert "errors" in response
    assert "Landscape Group not found" in response["errors"][0]["message"]
