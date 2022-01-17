import pytest

pytestmark = pytest.mark.django_db


def test_memberships_query(client_query, memberships):
    response = client_query(
        """
        {memberships {
          edges {
            node {
              group {
                slug
              }
              user {
                email
              }
              userRole
            }
          }
        }}
        """
    )
    edges = response.json()["data"]["memberships"]["edges"]
    nodes = [edge["node"] for edge in edges]

    memberships_returned = [(memb["group"]["slug"], memb["user"]["email"]) for memb in nodes]

    memberships_expected = [(memb.group.slug, memb.user.email) for memb in memberships]

    assert memberships_expected == memberships_returned


def test_membership_get_one_by_id(client_query, memberships):
    membership = memberships[0]
    query = (
        """
        {membership(id: "%s") {
          id
        }}
        """
        % membership.id
    )
    response = client_query(query)
    membership_result = response.json()["data"]["membership"]

    assert membership_result["id"] == str(membership.id)
