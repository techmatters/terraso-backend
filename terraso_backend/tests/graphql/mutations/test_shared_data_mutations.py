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

from apps.core.models import Membership
from apps.shared_data.models import DataEntry

pytestmark = pytest.mark.django_db


def test_add_data_entry(client_query, managed_groups):
    group = managed_groups[0]
    data = {
        "name": "Name",
        "description": "Description",
        "url": "https://example.com",
        "entryType": "link",
        "resourceType": "link",
        "groupSlug": group.slug,
    }
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
        variables={"input": data},
    )
    result = response.json()["data"]["addDataEntry"]
    assert result["errors"] is None
    assert result["dataEntry"]["name"] == data["name"]
    assert result["dataEntry"]["url"] == data["url"]


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

    data_entry_result = response.json()["data"]["deleteDataEntry"]["dataEntry"]

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
    old_data_entry.groups.first().add_manager(users[0])

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

    data_entry_result = response.json()["data"]["deleteDataEntry"]["dataEntry"]

    assert data_entry_result["name"] == old_data_entry.name
    assert not DataEntry.objects.filter(name=data_entry_result["name"])


def test_data_entry_delete_by_manager_fails_due_to_membership_approval_status(
    client_query, data_entries, users
):
    old_data_entry = data_entries[0]
    old_data_entry.created_by = users[2]
    old_data_entry.save()
    group = old_data_entry.groups.first()
    group.add_manager(users[0])
    users[0].memberships.filter(group=group).update(membership_status=Membership.PENDING)

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
