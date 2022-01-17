import pytest

pytestmark = pytest.mark.django_db


def test_group_associations_query(client_query, group_associations):
    response = client_query(
        """
        {groupAssociations {
          edges {
            node {
              parentGroup {
                slug
              }
              childGroup {
                slug
              }
            }
          }
        }}
        """
    )
    edges = response.json()["data"]["groupAssociations"]["edges"]
    nodes = [edge["node"] for edge in edges]

    associations_returned = [
        (assoc["parentGroup"]["slug"], assoc["childGroup"]["slug"]) for assoc in nodes
    ]

    associations_expected = [
        (assoc.parent_group.slug, assoc.child_group.slug) for assoc in group_associations
    ]

    assert associations_expected == associations_returned


def test_group_association_get_one_by_id(client_query, group_associations):
    group_association = group_associations[0]
    query = (
        """
        {groupAssociation(id: "%s") {
          id
        }}
        """
        % group_association.id
    )
    response = client_query(query)

    group_association_result = response.json()["data"]["groupAssociation"]

    assert group_association_result["id"] == str(group_association.id)
