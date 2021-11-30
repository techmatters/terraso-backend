import pytest

from apps.core.models import LandscapeGroup

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("is_default_group", (True, False))
def test_landscape_groups_add(client_query, landscapes, groups, is_default_group):
    landscape = landscapes[0]
    group = groups[0]

    response = client_query(
        """
        mutation addLandscapeGroup($input: LandscapeGroupAddMutationInput!){
          addLandscapeGroup(input: $input) {
            landscapeGroup {
              id
              landscape {
                name
              }
              group {
                name
              }
              isDefaultLandscapeGroup
            }
          }
        }
        """,
        variables={
            "input": {
                "landscapeSlug": landscape.slug,
                "groupSlug": group.slug,
                "isDefaultLandscapeGroup": is_default_group,
            }
        },
    )
    landscape_group = response.json()["data"]["addLandscapeGroup"]["landscapeGroup"]

    assert landscape_group["id"]
    assert landscape_group["landscape"]["name"] == landscape.name
    assert landscape_group["group"]["name"] == group.name
    assert landscape_group["isDefaultLandscapeGroup"] is is_default_group


def test_landscape_groups_add_without_default(client_query, landscapes, groups):
    landscape = landscapes[0]
    group = groups[0]

    response = client_query(
        """
        mutation addLandscapeGroup($input: LandscapeGroupAddMutationInput!){
          addLandscapeGroup(input: $input) {
            landscapeGroup {
              isDefaultLandscapeGroup
            }
          }
        }
        """,
        variables={
            "input": {
                "landscapeSlug": landscape.slug,
                "groupSlug": group.slug,
            }
        },
    )
    landscape_group = response.json()["data"]["addLandscapeGroup"]["landscapeGroup"]

    assert not landscape_group["isDefaultLandscapeGroup"]


def test_landscape_groups_update_is_default_group(client_query, landscape_groups):
    old_landscape_group = _get_landscape_groups(client_query)[0]
    old_is_default = old_landscape_group["isDefaultLandscapeGroup"]

    response = client_query(
        """
        mutation updateLandscapeGroup($input: LandscapeGroupUpdateMutationInput!){
          updateLandscapeGroup(input: $input) {
            landscapeGroup {
              id
              isDefaultLandscapeGroup
            }
          }
        }
        """,
        variables={
            "input": {
                "id": old_landscape_group["id"],
                "isDefaultLandscapeGroup": not old_is_default,
            }
        },
    )
    landscape_group = response.json()["data"]["updateLandscapeGroup"]["landscapeGroup"]

    assert landscape_group["id"] == old_landscape_group["id"]
    assert landscape_group["isDefaultLandscapeGroup"] is not old_is_default


def test_landscape_groups_update_landscape_and_group(
    client_query, landscapes, groups, landscape_groups
):
    old_landscape_group = _get_landscape_groups(client_query)[0]
    new_landscape = landscapes[-1]
    new_group = groups[-1]

    response = client_query(
        """
        mutation updateLandscapeGroup($input: LandscapeGroupUpdateMutationInput!){
          updateLandscapeGroup(input: $input) {
            landscapeGroup {
              id
              landscape { slug }
              group { slug }
            }
          }
        }
        """,
        variables={
            "input": {
                "id": old_landscape_group["id"],
                "landscapeSlug": new_landscape.slug,
                "groupSlug": new_group.slug,
            }
        },
    )
    landscape_group = response.json()["data"]["updateLandscapeGroup"]["landscapeGroup"]

    assert landscape_group["id"] == old_landscape_group["id"]
    assert landscape_group["landscape"]["slug"] == new_landscape.slug
    assert landscape_group["group"]["slug"] == new_group.slug


def test_landscape_groups_delete(client_query, landscape_groups):
    old_landscape_group = _get_landscape_groups(client_query)[0]
    response = client_query(
        """
        mutation deleteLandscapeGroup($input: LandscapeGroupDeleteMutationInput!){
          deleteLandscapeGroup(input: $input) {
            landscapeGroup {
              id
              landscape { slug }
              group { slug }
            }
          }
        }
        """,
        variables={"input": {"id": old_landscape_group["id"]}},
    )
    landscape_group = response.json()["data"]["deleteLandscapeGroup"]["landscapeGroup"]

    assert landscape_group["id"]
    assert not LandscapeGroup.objects.filter(
        landscape__slug=landscape_group["landscape"]["slug"],
        group__slug=landscape_group["group"]["slug"],
    )


def _get_landscape_groups(client_query):
    response = client_query(
        """
        {
          landscapeGroups {
            edges {
              node {
                id
                landscape { slug }
                isDefaultLandscapeGroup
                group { slug }
              }
            }
          }
        }
        """
    )
    edges = response.json()["data"]["landscapeGroups"]["edges"]
    return [e["node"] for e in edges]
