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
from apps.shared_data.models import DataEntry

pytestmark = pytest.mark.django_db


@pytest.fixture
def input_by_parent(request, managed_groups, managed_landscapes):
    parent = request.param
    return {
        "name": "Name",
        "description": "Description",
        "url": "https://example.com",
        "entryType": "link",
        "resourceType": "link",
        "targetType": "group" if parent == "group" else "landscape",
        "targetSlug": managed_groups[0].slug if parent == "group" else managed_landscapes[0].slug,
    }


@pytest.mark.parametrize("input_by_parent", ["group", "landscape"], indirect=True)
def test_add_data_entry(client_query, input_by_parent):
    response = client_query(
        """
        mutation addDataEntry($input: DataEntryAddMutationInput!) {
          addDataEntry(input: $input) {
            dataEntry {
              id
              name
              url
            }
            errors
          }
        }
        """,
        variables={"input": input_by_parent},
    )
    result = response.json()["data"]["addDataEntry"]
    assert result["errors"] is None
    assert result["dataEntry"]["name"] == input_by_parent["name"]
    assert result["dataEntry"]["url"] == input_by_parent["url"]


def test_data_entry_update_by_creator_works(client_query, data_entries):
    # The data entries' owner is the same user on client query
    old_data_entry = data_entries[0]

    new_data = {
        "id": str(old_data_entry.id),
        "description": "New description",
        "name": "New Name",
    }
    response = client_query(
        """
        mutation updateDataEntry($input: DataEntryUpdateMutationInput!) {
          updateDataEntry(input: $input) {
            dataEntry {
              id
              name
              description
            }
          }
        }
        """,
        variables={"input": new_data},
    )
    group_result = response.json()["data"]["updateDataEntry"]["dataEntry"]

    assert group_result == new_data


def test_data_entry_update_by_non_creator_fails_due_permission_check(
    client_query, data_entries, users
):
    old_data_entry = data_entries[0]

    # Let's force old data creator be different from client query user
    old_data_entry.created_by = users[2]
    old_data_entry.save()

    new_data = {
        "id": str(old_data_entry.id),
        "description": "New description",
    }

    response = client_query(
        """
        mutation updateDataEntry($input: DataEntryUpdateMutationInput!) {
          updateDataEntry(input: $input) {
            dataEntry {
              id
            }
            errors
          }
        }
        """,
        variables={"input": new_data},
    )
    response = response.json()

    assert "errors" in response["data"]["updateDataEntry"]
    assert "update_not_allowed" in response["data"]["updateDataEntry"]["errors"][0]["message"]


def test_data_entry_delete_by_creator_works(client_query, data_entries):
    old_data_entry = data_entries[0]

    response = client_query(
        """
        mutation deleteDataEntry($input: DataEntryDeleteMutationInput!){
          deleteDataEntry(input: $input) {
            dataEntry {
              name
            }
          }
        }

        """,
        variables={"input": {"id": str(old_data_entry.id)}},
    )

    json_response = response.json()
    data_entry_result = json_response["data"]["deleteDataEntry"]["dataEntry"]

    assert data_entry_result["name"] == old_data_entry.name
    assert not DataEntry.objects.filter(name=data_entry_result["name"])


def test_data_entry_delete_by_non_creator_fails_due_permission_check(
    client_query, data_entries, users
):
    old_data_entry = data_entries[0]

    # Let's force old data creator be different from client query user
    old_data_entry.created_by = users[2]
    old_data_entry.save()

    response = client_query(
        """
        mutation deleteDataEntry($input: DataEntryDeleteMutationInput!){
          deleteDataEntry(input: $input) {
            dataEntry {
              name
            }
            errors
          }
        }

        """,
        variables={"input": {"id": str(old_data_entry.id)}},
    )

    response = response.json()

    assert "errors" in response["data"]["deleteDataEntry"]
    assert "delete_not_allowed" in response["data"]["deleteDataEntry"]["errors"][0]["message"]


def test_data_entry_delete_by_manager_works(client_query, data_entries, users, groups):
    old_data_entry = data_entries[0]
    old_data_entry.created_by = users[2]
    old_data_entry.save()
    groups[0].add_manager(users[0])

    response = client_query(
        """
        mutation deleteDataEntry($input: DataEntryDeleteMutationInput!){
          deleteDataEntry(input: $input) {
            dataEntry {
              name
            }
            errors
          }
        }

        """,
        variables={"input": {"id": str(old_data_entry.id)}},
    )

    json_response = response.json()
    data_entry_result = json_response["data"]["deleteDataEntry"]["dataEntry"]

    assert data_entry_result["name"] == old_data_entry.name
    assert not DataEntry.objects.filter(name=data_entry_result["name"])


@pytest.fixture
def data_entry_by_not_manager_by_owner(request, users, landscape_data_entries, group_data_entries):
    owner = request.param

    (data_entry, target) = (
        (group_data_entries[0], group_data_entries[0].shared_resources.first().target)
        if owner == "group"
        else (
            landscape_data_entries[0],
            landscape_data_entries[0].shared_resources.first().target,
        )
    )

    data_entry.created_by = users[2]
    data_entry.save()
    target.membership_list.memberships.filter(user=users[0]).update(
        membership_status=CollaborationMembership.PENDING
    )
    return data_entry


@pytest.mark.parametrize(
    "data_entry_by_not_manager_by_owner", ["group", "landscape"], indirect=True
)
def test_data_entry_delete_by_manager_fails_due_to_membership_approval_status(
    client_query, data_entry_by_not_manager_by_owner
):
    old_data_entry = data_entry_by_not_manager_by_owner

    response = client_query(
        """
        mutation deleteDataEntry($input: DataEntryDeleteMutationInput!){
          deleteDataEntry(input: $input) {
            dataEntry {
              name
            }
            errors
          }
        }

        """,
        variables={"input": {"id": str(old_data_entry.id)}},
    )

    response = response.json()

    assert "errors" in response["data"]["deleteDataEntry"]
    assert "delete_not_allowed" in response["data"]["deleteDataEntry"]["errors"][0]["message"]


def test_data_entry_delete_not_showing_in_query(
    client_query, landscape_data_entries, users, landscapes
):
    old_data_entry = landscape_data_entries[0]

    assert landscapes[0].shared_resources.filter(source_object_id=old_data_entry.id).exists()

    response = client_query(
        """
        mutation deleteDataEntry($input: DataEntryDeleteMutationInput!){
          deleteDataEntry(input: $input) {
            dataEntry {
              name
            }
            errors
          }
        }

        """,
        variables={"input": {"id": str(old_data_entry.id)}},
    )

    json_response = response.json()
    data_entry_result = json_response["data"]["deleteDataEntry"]["dataEntry"]

    assert data_entry_result["name"] == old_data_entry.name
    assert not DataEntry.objects.filter(name=data_entry_result["name"])

    assert not landscapes[0].shared_resources.filter(source_object_id=old_data_entry.id).exists()
