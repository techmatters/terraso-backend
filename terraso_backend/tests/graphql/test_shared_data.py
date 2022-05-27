import pytest

pytestmark = pytest.mark.django_db


def test_data_entries_query(client_query, data_entries):
    response = client_query(
        """
        {dataEntries {
          edges {
            node {
              name
            }
          }
        }}
        """
    )

    edges = response.json()["data"]["dataEntries"]["edges"]
    entries_result = [edge["node"]["name"] for edge in edges]

    for data_entry in data_entries:
        assert data_entry.name in entries_result


def test_data_entry_get_one_by_id(client_query, data_entries):
    data_entry = data_entries[0]
    query = (
        """
        {dataEntry(id: "%s") {
          id
          name
        }}
        """
        % data_entry.id
    )
    response = client_query(query)
    data_entry_result = response.json()["data"]["dataEntry"]

    assert data_entry_result["id"] == str(data_entry.id)
    assert data_entry_result["name"] == data_entry.name


def test_data_entries_query_has_total_count(client_query, data_entries):
    response = client_query(
        """
        {dataEntries {
          totalCount
          edges {
            node {
              name
            }
          }
        }}
        """
    )
    total_count = response.json()["data"]["dataEntries"]["totalCount"]

    assert total_count == len(data_entries)


def test_data_entries_filter_by_group_slug_filters_successfuly(client_query, data_entries, groups):
    data_entry_a = data_entries[0]
    data_entry_b = data_entries[1]

    data_entry_a.groups.add(groups[-1])
    data_entry_b.groups.add(groups[-1])

    group_filter = groups[-1]

    response = client_query(
        """
        {dataEntries(groups_Slug_Icontains: "%s") {
          edges {
            node {
              id
            }
          }
        }}
        """
        % group_filter.slug
    )

    edges = response.json()["data"]["dataEntries"]["edges"]
    data_entries_result = [edge["node"]["id"] for edge in edges]

    assert len(data_entries_result) == 2
    assert str(data_entry_a.id) in data_entries_result
    assert str(data_entry_b.id) in data_entries_result


def test_data_entries_filter_by_group_id_filters_successfuly(client_query, data_entries, groups):
    data_entry_a = data_entries[0]
    data_entry_b = data_entries[1]

    data_entry_a.groups.add(groups[-1])
    data_entry_b.groups.add(groups[-1])

    group_filter = groups[-1]

    response = client_query(
        """
        {dataEntries(groups_Id: "%s") {
          edges {
            node {
              id
            }
          }
        }}
        """
        % group_filter.id
    )

    edges = response.json()["data"]["dataEntries"]["edges"]
    data_entries_result = [edge["node"]["id"] for edge in edges]

    assert len(data_entries_result) == 2
    assert str(data_entry_a.id) in data_entries_result
    assert str(data_entry_b.id) in data_entries_result


def test_data_entries_returns_only_for_users_groups(
    client_query, data_entry_current_user, data_entry_other_user
):
    # It's being done a request for all data entries, but only the data entries
    # from logged user's group is expected to return.
    response = client_query(
        """
        {dataEntries {
          edges {
            node {
              id
            }
          }
        }}
        """
    )

    edges = response.json()["data"]["dataEntries"]["edges"]
    entries_result = [edge["node"]["id"] for edge in edges]

    assert len(entries_result) == 1
    assert entries_result[0] == str(data_entry_current_user.id)
