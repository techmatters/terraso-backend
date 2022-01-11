import pytest

from apps.core.models import GroupAssociation

pytestmark = pytest.mark.django_db


def test_group_associations_add(client_query, groups):
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


def test_group_associations_add_duplicated(client_query, group_associations):
    parent_group = group_associations[0].parent_group
    child_group = group_associations[0].child_group

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

    assert "Parent group and Child group already exists" in error_result["message"]


def test_group_associations_delete(client_query, group_associations):
    old_group_association = group_associations[0]
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
