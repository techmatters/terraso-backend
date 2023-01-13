import pytest

from apps.core.models import GroupAssociation

pytestmark = pytest.mark.django_db


def test_group_associations_add_by_parent_manager(client_query, users, groups):
    user = users[0]
    parent_group = groups[0]
    child_group = groups[1]

    parent_group.add_manager(user)

    response = client_query(
        """
        mutation addGroupAssociation($input: GroupAssociationAddMutationInput!){
          addGroupAssociation(input: $input) {
            groupAssociation {
              id
              parentGroup { slug }
              childGroup { slug }
            }
          }
        }
        """,
        variables={
            "input": {
                "parentGroupSlug": parent_group.slug,
                "childGroupSlug": child_group.slug,
            }
        },
    )
    group_association = response.json()["data"]["addGroupAssociation"]["groupAssociation"]

    assert group_association["id"]
    assert group_association["parentGroup"]["slug"] == parent_group.slug
    assert group_association["childGroup"]["slug"] == child_group.slug


def test_group_associations_add_by_non_parent_manager_fails(client_query, groups):
    parent_group = groups[0]
    child_group = groups[1]

    response = client_query(
        """
        mutation addGroupAssociation($input: GroupAssociationAddMutationInput!){
          addGroupAssociation(input: $input) {
            groupAssociation {
              id
              parentGroup { slug }
              childGroup { slug }
            }
            errors
          }
        }
        """,
        variables={
            "input": {
                "parentGroupSlug": parent_group.slug,
                "childGroupSlug": child_group.slug,
            }
        },
    )
    response = response.json()

    assert "errors" in response["data"]["addGroupAssociation"]
    assert "create_not_allowed" in response["data"]["addGroupAssociation"]["errors"][0]["message"]


def test_group_associations_add_duplicated(client_query, users, group_associations):
    user = users[0]
    parent_group = group_associations[0].parent_group
    child_group = group_associations[0].child_group

    parent_group.add_manager(user)

    response = client_query(
        """
        mutation addGroupAssociation($input: GroupAssociationAddMutationInput!){
          addGroupAssociation(input: $input) {
            groupAssociation {
              id
              parentGroup { slug }
              childGroup { slug }
            }
            errors
          }
        }
        """,
        variables={
            "input": {
                "parentGroupSlug": parent_group.slug,
                "childGroupSlug": child_group.slug,
            }
        },
    )

    error_result = response.json()["data"]["addGroupAssociation"]["errors"][0]

    assert "duplicate key value" in error_result["message"]


def test_group_associations_add_parent_group_not_found(client_query, groups):
    child_group = groups[1]

    response = client_query(
        """
        mutation addGroupAssociation($input: GroupAssociationAddMutationInput!){
          addGroupAssociation(input: $input) {
            groupAssociation {
              id
              parentGroup { slug }
              childGroup { slug }
            }
            errors
          }
        }
        """,
        variables={
            "input": {
                "parentGroupSlug": "non-existing-group",
                "childGroupSlug": child_group.slug,
            }
        },
    )
    response = response.json()

    assert "errors" in response["data"]["addGroupAssociation"]
    assert "not_found" in response["data"]["addGroupAssociation"]["errors"][0]["message"]


def test_group_associations_add_child_group_not_found(client_query, groups):
    parent_group = groups[0]

    response = client_query(
        """
        mutation addGroupAssociation($input: GroupAssociationAddMutationInput!){
          addGroupAssociation(input: $input) {
            groupAssociation {
              id
              parentGroup { slug }
              childGroup { slug }
            }
            errors
          }
        }
        """,
        variables={
            "input": {
                "parentGroupSlug": parent_group.slug,
                "childGroupSlug": "non-existing-group",
            }
        },
    )
    response = response.json()

    assert "errors" in response["data"]["addGroupAssociation"]
    assert "not_found" in response["data"]["addGroupAssociation"]["errors"][0]["message"]


def test_group_associations_delete_by_parent_manager(client_query, users, group_associations):
    user = users[0]
    old_group_association = group_associations[0]
    old_group_association.parent_group.add_manager(user)

    response = client_query(
        """
        mutation deleteGroupAssociation($input: GroupAssociationDeleteMutationInput!){
          deleteGroupAssociation(input: $input) {
            groupAssociation {
              parentGroup { slug }
              childGroup { slug }
            }
          }
        }
        """,
        variables={"input": {"id": str(old_group_association.id)}},
    )
    group_association = response.json()["data"]["deleteGroupAssociation"]["groupAssociation"]

    assert not GroupAssociation.objects.filter(
        parent_group__slug=group_association["parentGroup"]["slug"],
        child_group__slug=group_association["childGroup"]["slug"],
    )


def test_group_associations_delete_by_child_manager(client_query, users, group_associations):
    user = users[0]
    old_group_association = group_associations[0]
    old_group_association.child_group.add_manager(user)

    response = client_query(
        """
        mutation deleteGroupAssociation($input: GroupAssociationDeleteMutationInput!){
          deleteGroupAssociation(input: $input) {
            groupAssociation {
              parentGroup { slug }
              childGroup { slug }
            }
          }
        }
        """,
        variables={"input": {"id": str(old_group_association.id)}},
    )
    group_association = response.json()["data"]["deleteGroupAssociation"]["groupAssociation"]

    assert not GroupAssociation.objects.filter(
        parent_group__slug=group_association["parentGroup"]["slug"],
        child_group__slug=group_association["childGroup"]["slug"],
    )


def test_group_associations_delete_by_non_manager_fail(client_query, group_associations):
    old_group_association = group_associations[0]

    response = client_query(
        """
        mutation deleteGroupAssociation($input: GroupAssociationDeleteMutationInput!){
          deleteGroupAssociation(input: $input) {
            groupAssociation {
              parentGroup { slug }
              childGroup { slug }
            }
            errors
          }
        }
        """,
        variables={"input": {"id": str(old_group_association.id)}},
    )
    response = response.json()

    assert "errors" in response["data"]["deleteGroupAssociation"]
    assert (
        "delete_not_allowed" in response["data"]["deleteGroupAssociation"]["errors"][0]["message"]
    )
