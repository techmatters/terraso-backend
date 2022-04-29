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
