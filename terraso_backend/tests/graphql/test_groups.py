import pytest

pytestmark = pytest.mark.django_db


def test_groups_query(client_query, groups):
    response = client_query(
        """
        {groups {
          edges {
            node {
              slug
            }
          }
        }}
        """
    )
    edges = response.json()["data"]["groups"]["edges"]
    groups_result = [edge["node"]["slug"] for edge in edges]

    for group in groups:
        assert group.slug in groups_result


def test_group_get_by_one_by_id(client_query, groups):
    group = groups[0]
    query = (
        """
        {group(id: "%s") {
          id
          slug
        }}
        """
        % group.id
    )
    response = client_query(query)
    group_result = response.json()["data"]["group"]

    assert group_result["id"] == str(group.id)
    assert group_result["slug"] == group.slug
