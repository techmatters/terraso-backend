import pytest

pytestmark = pytest.mark.django_db


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


def test_users_query_has_total_count(client_query, users):
    response = client_query(
        """
        {users {
          totalCount
          edges {
            node {
              email
            }
          }
        }}
        """
    )
    total_count = response.json()["data"]["users"]["totalCount"]

    assert total_count == len(users)
