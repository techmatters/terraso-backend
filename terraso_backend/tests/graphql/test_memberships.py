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

    memberships_email_returned = [
        (memb["group"]["slug"], memb["user"]["email"]) for memb in nodes
    ].sort()

    memberships_email_expected = [(memb.group.slug, memb.user.email) for memb in memberships].sort()

    assert memberships_email_returned == memberships_email_expected


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


def test_memberships_query_has_total_count(client_query, memberships):
    response = client_query(
        """
        {memberships {
          totalCount
          edges {
            node {
              id
            }
          }
        }}
        """
    )
    total_count = response.json()["data"]["memberships"]["totalCount"]

    assert total_count == len(memberships)
