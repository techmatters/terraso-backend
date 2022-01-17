import pytest

pytestmark = pytest.mark.django_db


def test_landscapes_query(client_query, landscapes):
    response = client_query(
        """
        {landscapes {
          edges {
            node {
              slug
            }
          }
        }}
        """
    )
    edges = response.json()["data"]["landscapes"]["edges"]
    landscapes_result = [edge["node"]["slug"] for edge in edges]

    for landscape in landscapes:
        assert landscape.slug in landscapes_result


def test_landscape_get_one_by_id(client_query, landscapes):
    landscape = landscapes[0]
    query = (
        """
        {landscape(id: "%s") {
            id
            slug
          }
        }
        """
        % landscape.id
    )
    response = client_query(query)
    landscape_result = response.json()["data"]["landscape"]

    assert landscape_result["id"] == str(landscape.id)
    assert landscape_result["slug"] == landscape.slug


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


def test_landscape_group_get_one_by_id(client_query, landscape_groups):
    landscape_group = landscape_groups[0]
    query = (
        """
        {landscapeGroup(id: "%s") {
          id
        }}
        """
        % landscape_group.id
    )
    response = client_query(query)

    landscape_group_response = response.json()["data"]["landscapeGroup"]

    assert landscape_group_response["id"] == str(landscape_group.id)


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


def test_users_query(client_query, users):
    response = client_query(
        """
        {users {
          edges {
            node {
              email
              profileImage
            }
          }
        }}
        """
    )
    edges = response.json()["data"]["users"]["edges"]
    users_result_nodes = [edge["node"] for edge in edges]
    for user in users:
        user_node = next(item for item in users_result_nodes if item["email"] == user.email)
        assert user_node
        assert user.profile_image == user_node["profileImage"]


def test_user_get_one_by_id(client_query, users):
    user = users[0]
    query = (
        """
        {user(id: "%s") {
          id
          email
          profileImage
        }}
        """
        % user.id
    )
    response = client_query(query)
    user_result = response.json()["data"]["user"]
    assert user_result["id"] == str(user.id)
    assert user_result["email"] == user.email
    assert user_result["profileImage"] == user.profile_image
