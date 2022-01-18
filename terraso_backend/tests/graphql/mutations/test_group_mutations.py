import pytest

from apps.core.models import Group

pytestmark = pytest.mark.django_db


def test_groups_add(client_query):
    group_name = "Testing Group"
    response = client_query(
        """
        mutation addGroup($input: GroupAddMutationInput!){
          addGroup(input: $input) {
            group {
              id
              name
            }
          }
        }
        """,
        variables={"input": {"name": group_name}},
    )
    group_result = response.json()["data"]["addGroup"]["group"]

    assert group_result["id"]
    assert group_result["name"] == group_name


def test_groups_add_has_created_by_filled_out(client_query, users):
    group_name = "Testing Group"
    group_creator = users[0]

    response = client_query(
        """
        mutation addGroup($input: GroupAddMutationInput!){
          addGroup(input: $input) {
            group {
              id
              name
              createdBy { email }
            }
          }
        }
        """,
        variables={"input": {"name": group_name}},
    )
    group_result = response.json()["data"]["addGroup"]["group"]

    assert group_result["id"]
    assert group_result["name"] == group_name
    assert group_result["createdBy"]["email"] == group_creator.email


def test_groups_add_duplicated(client_query, groups):
    group_name = groups[0].name
    response = client_query(
        """
        mutation addGroup($input: GroupAddMutationInput!){
          addGroup(input: $input) {
            group {
              id
              name
            }
          }
        }
        """,
        variables={"input": {"name": group_name}},
    )
    error_result = response.json()["errors"][0]

    assert error_result
    assert "field=name" in error_result["message"]


def test_groups_update_by_manager_works(client_query, groups, users):
    old_group = groups[0]
    # Makes sure user is group manager before update
    old_group.add_manager(users[0])

    new_data = {
        "id": str(old_group.id),
        "description": "New description",
        "name": "New Name",
        "website": "https://www.example.com/updated-group",
        "email": "a-new-email@example.com",
    }
    response = client_query(
        """
        mutation updateGroup($input: GroupUpdateMutationInput!) {
          updateGroup(input: $input) {
            group {
              id
              name
              description
              website
              email
            }
          }
        }
        """,
        variables={"input": new_data},
    )
    group_result = response.json()["data"]["updateGroup"]["group"]

    assert group_result == new_data


def test_groups_update_by_member_fails_due_permission_check(client_query, groups):
    old_group = groups[0]
    new_data = {
        "id": str(old_group.id),
        "description": "New description",
    }
    response = client_query(
        """
        mutation updateGroup($input: GroupUpdateMutationInput!) {
          updateGroup(input: $input) {
            group {
              id
            }
          }
        }
        """,
        variables={"input": new_data},
    )
    response = response.json()

    assert "errors" in response
    assert "has no permission to change" in response["errors"][0]["message"]


def test_groups_delete(client_query, groups):
    old_group = groups[0]
    response = client_query(
        """
        mutation deleteGroup($input: GroupDeleteMutationInput!){
          deleteGroup(input: $input) {
            group {
              slug
            }
          }
        }

        """,
        variables={"input": {"id": str(old_group.id)}},
    )

    group_result = response.json()["data"]["deleteGroup"]["group"]

    assert group_result["slug"] == old_group.slug
    assert not Group.objects.filter(slug=group_result["slug"])
