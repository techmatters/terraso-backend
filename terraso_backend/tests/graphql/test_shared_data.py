import pytest

pytestmark = pytest.mark.django_db


def test_data_entries_query(client_query, data_entries):
    response = client_query(
        """
        {dataEntries {
          edges {
            node {
              slug
            }
          }
        }}
        """
    )

    edges = response.json()["data"]["dataEntries"]["edges"]
    entries_result = [edge["node"]["slug"] for edge in edges]

    for data_entry in data_entries:
        assert data_entry.slug in entries_result


def test_data_entry_get_one_by_id(client_query, data_entries):
    data_entry = data_entries[0]
    query = (
        """
        {dataEntry(id: "%s") {
          id
          slug
        }}
        """
        % data_entry.id
    )
    response = client_query(query)
    data_entry_result = response.json()["data"]["dataEntry"]

    assert data_entry_result["id"] == str(data_entry.id)
    assert data_entry_result["slug"] == data_entry.slug


def test_data_entries_query_has_total_count(client_query, data_entries):
    response = client_query(
        """
        {dataEntries {
          totalCount
          edges {
            node {
              slug
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

    data_entry_a.groups.add(*groups)
    data_entry_b.groups.add(*groups)

    group_filter = groups[0]

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

    data_entry_a.groups.add(*groups)
    data_entry_b.groups.add(*groups)

    group_filter = groups[0]

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


def test_data_entries_filter_by_group_slug_returns_empty_if_no_associations(
    client_query, data_entries, groups
):
    # All data entries aren't associated to any group, the result must be empty
    group_filter = groups[0]

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

    assert not response.json()["data"]["dataEntries"]["edges"]


def test_data_entries_filter_by_group_id_returns_empty_if_no_associations(
    client_query, data_entries, groups
):
    # All data entries aren't associated to any group, the result must be empty
    group_filter = groups[0]

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

    assert not response.json()["data"]["dataEntries"]["edges"]
