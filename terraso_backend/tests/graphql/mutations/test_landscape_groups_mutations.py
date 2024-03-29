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

import uuid

import pytest
from mixer.backend.django import mixer

from apps.collaboration.models import Membership as CollaborationMembership
from apps.core import landscape_collaboration_roles
from apps.core.models import Group, LandscapeGroup

pytestmark = pytest.mark.django_db


def test_landscape_groups_add_by_landscape_manager(client_query, managed_landscapes, groups):
    landscape = managed_landscapes[0]
    group = groups[0]

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


def test_landscape_groups_add_by_non_landscape_manager_not_allowed(
    client_query, landscapes, groups
):
    landscape = landscapes[0]
    group = groups[0]

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
            }
            errors
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

    assert "errors" in response["data"]["addLandscapeGroup"]
    assert "create_not_allowed" in response["data"]["addLandscapeGroup"]["errors"][0]["message"]


def test_landscape_groups_add_duplicated(client_query, users, landscape_common_group):
    user = users[0]
    landscape = landscape_common_group.landscape
    landscape.membership_list.save_membership(
        user.email, landscape_collaboration_roles.ROLE_MANAGER, CollaborationMembership.APPROVED
    )

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
            }
            errors
          }
        }
        """,
        variables={
            "input": {
                "landscapeSlug": landscape.slug,
                "groupSlug": landscape_common_group.group.slug,
            }
        },
    )
    error_result = response.json()["data"]["addLandscapeGroup"]["errors"][0]

    assert "duplicate key" in error_result["message"]


def test_landscape_groups_add_landscape_not_found(client_query, groups):
    group = groups[0]

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
            }
            errors
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

    assert "errors" in response["data"]["addLandscapeGroup"]
    assert "not_found" in response["data"]["addLandscapeGroup"]["errors"][0]["message"]


def test_landscape_groups_add_group_not_found(client_query, managed_landscapes):
    landscape = managed_landscapes[0]

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
            }
            errors
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

    assert "errors" in response["data"]["addLandscapeGroup"]
    assert "not_found" in response["data"]["addLandscapeGroup"]["errors"][0]["message"]


def test_landscape_groups_delete_by_group_manager(client_query, users, landscape_common_group):
    user = users[0]
    old_landscape_group = landscape_common_group
    old_landscape_group.group.add_manager(user)

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


def test_landscape_groups_delete_by_landscape_manager(client_query, users, managed_landscapes):
    landscape = managed_landscapes[0]
    group = mixer.blend(Group)
    old_landscape_group = mixer.blend(LandscapeGroup, landscape=landscape, group=group)

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
    client_query, users, landscape_common_group
):
    old_landscape_group = landscape_common_group

    response = client_query(
        """
        mutation deleteLandscapeGroup($input: LandscapeGroupDeleteMutationInput!){
          deleteLandscapeGroup(input: $input) {
            landscapeGroup {
              landscape { slug }
              group { slug }
            }
            errors
          }
        }
        """,
        variables={"input": {"id": str(old_landscape_group.id)}},
    )
    response = response.json()

    assert "errors" in response["data"]["deleteLandscapeGroup"]
    assert "delete_not_allowed" in response["data"]["deleteLandscapeGroup"]["errors"][0]["message"]


def test_landscape_groups_delete_not_found(client_query, users):
    response = client_query(
        """
        mutation deleteLandscapeGroup($input: LandscapeGroupDeleteMutationInput!){
          deleteLandscapeGroup(input: $input) {
            landscapeGroup {
              landscape { slug }
              group { slug }
            }
            errors
          }
        }
        """,
        variables={"input": {"id": str(uuid.uuid4())}},
    )
    response = response.json()

    assert "errors" in response["data"]["deleteLandscapeGroup"]
    assert "not_found" in response["data"]["deleteLandscapeGroup"]["errors"][0]["message"]
