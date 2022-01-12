import pytest

pytestmark = pytest.mark.django_db


def test_landscapes_query(client_query, landscapes):
    response = client_query(
        """
        query {
            landscapes {
                edges {
                    node {
                        slug
                    }
                }
            }
        }
        """
    )
    edges = response.json()["data"]["landscapes"]["edges"]
    landscapes_result = [edge["node"]["slug"] for edge in edges]

    for landscape in landscapes:
        assert landscape.slug in landscapes_result


def test_landscape_groups_query(client_query, landscape_groups):
    response = client_query(
        """
        {landscapeGroups {
          edges {
            node {
              landscape {
                slug
              }
              group {
                slug
              }
              isDefaultLandscapeGroup
            }
          }
        }}
        """
    )
    edges = response.json()["data"]["landscapeGroups"]["edges"]
    nodes = [edge["node"] for edge in edges]

    landscapes_and_groups_returned = [
        (lsg["landscape"]["slug"], lsg["group"]["slug"]) for lsg in nodes
    ]

    landscapes_and_groups_expected = [
        (lsg.landscape.slug, lsg.group.slug) for lsg in landscape_groups
    ]

    assert landscapes_and_groups_expected == landscapes_and_groups_returned


def test_groups_query(client_query, groups):
    response = client_query(
        """
        query {
            groups {
                edges {
                    node {
                        slug
                    }
                }
            }
        }
        """
    )
    edges = response.json()["data"]["groups"]["edges"]
    groups_result = [edge["node"]["slug"] for edge in edges]

    for group in groups:
        assert group.slug in groups_result


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


def test_users_query(client_query, users):
    response = client_query(
        """
        query {
            users {
                edges {
                    node {
                        email
                        profileImage
                    }
                }
            }
        }
        """
    )
    edges = response.json()["data"]["users"]["edges"]
    users_result_nodes = [edge["node"] for edge in edges]
    for user in users:
        user_node = next(item for item in users_result_nodes if item["email"] == user.email)
        assert user_node
        assert user.profile_image == user_node["profileImage"]
