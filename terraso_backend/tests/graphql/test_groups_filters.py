import pytest
from mixer.backend.django import mixer

from apps.core.models import Group, Membership

pytestmark = pytest.mark.django_db


def test_groups_filter_by_membership_user_ignores_deleted_memberships(client_query, memberships):
    membership = memberships[0]
    membership.delete()

    response = client_query(
        """
        {groups(memberships_Email: "%s") {
          edges {
            node {
              slug
            }
          }
        }}
        """
        % membership.user.email
    )
    edges = response.json()["data"]["groups"]["edges"]

    assert not edges


def test_groups_filter_by_with_landscape_association(client_query, users, landscape_groups):
    user = users[0]
    default_group_association, common_group_association = landscape_groups
    mixer.blend(Membership, user=user, group=default_group_association.group)
    mixer.blend(Membership, user=user, group=common_group_association.group)

    response = client_query(
        """
        {groups(
          associatedLandscapes_Isnull: false,
          memberships_Email: "%s"
        ) {
          edges {
            node {
              slug
            }
          }
        }}
        """
        % user.email
    )
    edges = response.json()["data"]["groups"]["edges"]
    groups_result = [edge["node"]["slug"] for edge in edges]

    assert len(groups_result) == 2
    assert default_group_association.group.slug in groups_result
    assert common_group_association.group.slug in groups_result


def test_groups_filter_by_with_landscape_association_ignores_deleted_associations(
    client_query, users, landscape_groups
):
    user = users[0]
    default_group_association, common_group_association = landscape_groups
    mixer.blend(Membership, user=user, group=default_group_association.group)
    mixer.blend(Membership, user=user, group=common_group_association.group)

    default_group_association.delete()

    response = client_query(
        """
        {groups(
          associatedLandscapes_Isnull: false,
          memberships_Email: "%s"
        ) {
          edges {
            node {
              slug
            }
          }
        }}
        """
        % user.email
    )
    edges = response.json()["data"]["groups"]["edges"]
    groups_result = [edge["node"]["slug"] for edge in edges]

    assert len(groups_result) == 1


def test_groups_filter_by_default_landscape_group(client_query, users, landscape_groups):
    user = users[0]
    default_group_association, common_group_association = landscape_groups
    mixer.blend(Membership, user=user, group=default_group_association.group)
    mixer.blend(Membership, user=user, group=common_group_association.group)

    response = client_query(
        """
        {groups(
          associatedLandscapes_IsDefaultLandscapeGroup: true,
          memberships_Email: "%s"
        ) {
          edges {
            node {
              slug
            }
          }
        }}
        """
        % user.email
    )
    edges = response.json()["data"]["groups"]["edges"]
    groups_result = [edge["node"]["slug"] for edge in edges]

    assert len(groups_result) == 1
    assert default_group_association.group.slug in groups_result


def test_groups_filter_by_without_landscape_association(client_query, users):
    user = users[0]
    group = mixer.blend(Group)
    membership = mixer.blend(Membership, user=user, group=group)

    response = client_query(
        """
        {groups(
          associatedLandscapes_Isnull: true,
          memberships_Email: "%s"
        ) {
          edges {
            node {
              slug
            }
          }
        }}
        """
        % membership.user.email
    )
    edges = response.json()["data"]["groups"]["edges"]
    groups_result = [edge["node"]["slug"] for edge in edges]
    assert len(groups_result) == 1
    assert groups_result[0] == group.slug
