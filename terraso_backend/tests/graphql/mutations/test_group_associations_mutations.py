import pytest

from apps.core.models import GroupAssociation

pytestmark = pytest.mark.django_db


def test_group_associations_add_by_parent_manager(settings, client_query, users, groups):
    user = users[0]
    parent_group = groups[0]
    child_group = groups[1]

    parent_group.add_manager(user)

    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

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


def test_group_associations_add_by_non_parent_manager_fails(settings, client_query, groups):
    parent_group = groups[0]
    child_group = groups[1]

    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

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
    response = response.json()

    assert "errors" in response
    assert "not_allowed" in response["errors"][0]["message"]


def test_group_associations_add_duplicated(settings, client_query, users, group_associations):
    user = users[0]
    parent_group = group_associations[0].parent_group
    child_group = group_associations[0].child_group

    parent_group.add_manager(user)

    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

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

    error_result = response.json()["errors"][0]

    assert "duplicate key value" in error_result["message"]


def test_group_associations_add_parent_group_not_found(settings, client_query, groups):
    child_group = groups[1]

    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

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
                "parentGroupSlug": "non-existing-group",
                "childGroupSlug": child_group.slug,
            }
        },
    )
    response = response.json()

    assert "errors" in response
    assert "not_found" in response["errors"][0]["message"]


def test_group_associations_add_child_group_not_found(settings, client_query, groups):
    parent_group = groups[0]

    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

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
                "childGroupSlug": "non-existing-group",
            }
        },
    )
    response = response.json()

    assert "errors" in response
    assert "not_found" in response["errors"][0]["message"]


def test_group_associations_delete_by_parent_manager(
    settings, client_query, users, group_associations
):
    user = users[0]
    old_group_association = group_associations[0]
    old_group_association.parent_group.add_manager(user)

    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

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


def test_group_associations_delete_by_child_manager(
    settings, client_query, users, group_associations
):
    user = users[0]
    old_group_association = group_associations[0]
    old_group_association.child_group.add_manager(user)

    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

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


def test_group_associations_delete_by_non_manager_fail(settings, client_query, group_associations):
    old_group_association = group_associations[0]

    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

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
    response = response.json()

    assert "errors" in response
    assert "not_allowed" in response["errors"][0]["message"]
