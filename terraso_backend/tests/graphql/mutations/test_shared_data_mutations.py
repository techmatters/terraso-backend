import pytest

from apps.shared_data.models import DataEntry

pytestmark = pytest.mark.django_db


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
          }
        }
        """,
        variables={"input": new_data},
    )
    response = response.json()

    assert "errors" in response
    assert "update_not_allowed" in response["errors"][0]["message"]


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
          }
        }

        """,
        variables={"input": {"id": str(old_data_entry.id)}},
    )

    response = response.json()

    assert "errors" in response
    assert "delete_not_allowed" in response["errors"][0]["message"]
