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


def test_group_associations_delete(client_query, group_associations):
    old_group_association = _get_group_associations(client_query)[0]
    response = client_query(
        """
        mutation deleteGroupAssociation($input: GroupAssociationDeleteMutationInput!){
          deleteGroupAssociation(input: $input) {
            groupAssociation {
              id
              parentGroup { slug }
              childGroup { slug }
            }
          }
        }
        """,
        variables={"input": {"id": old_group_association["id"]}},
    )
    group_association = response.json()["data"]["deleteGroupAssociation"]["groupAssociation"]

    assert group_association["id"]
    assert not GroupAssociation.objects.filter(
        parent_group__slug=group_association["parentGroup"]["slug"],
        child_group__slug=group_association["childGroup"]["slug"],
    )


def _get_group_associations(client_query):
    response = client_query(
        """
        {
          groupAssociations {
            edges {
              node {
                id
                parentGroup { slug }
                childGroup { slug }
              }
            }
          }
        }
        """
    )
    edges = response.json()["data"]["groupAssociations"]["edges"]
    return [e["node"] for e in edges]
