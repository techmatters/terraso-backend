import pytest
from mixer.backend.django import mixer

from apps.core.models import Membership

pytestmark = pytest.mark.django_db


def test_membership_add(client_query, groups, users):
    group = groups[0]
    user = users[0]

    response = client_query(
        """
        mutation addMembership($input: MembershipAddMutationInput!){
          addMembership(input: $input) {
            membership {
              id
              userRole
              user {
                email
              }
              group {
                slug
              }
            }
          }
        }
        """,
        variables={
            "input": {
                "userEmail": user.email,
                "groupSlug": group.slug,
            }
        },
    )
    membership = response.json()["data"]["addMembership"]["membership"]

    assert membership["id"]
    assert membership["user"]["email"] == user.email
    assert membership["group"]["slug"] == group.slug
    assert membership["userRole"] == Membership.ROLE_MEMBER.upper()


def test_membership_adding_duplicated_returns_previously_created(client_query, memberships):
    membership = memberships[0]
    group = membership.group
    user = membership.user

    response = client_query(
        """
        mutation addMembership($input: MembershipAddMutationInput!){
          addMembership(input: $input) {
            membership {
              id
              userRole
              user {
                email
              }
              group {
                slug
              }
            }
          }
        }
        """,
        variables={
            "input": {
                "userEmail": user.email,
                "groupSlug": group.slug,
            }
        },
    )
    membership_response = response.json()["data"]["addMembership"]["membership"]

    assert membership_response["id"] == str(membership.id)
    assert membership_response["userRole"] == membership.user_role.upper()
    assert membership_response["user"]["email"] == user.email
    assert membership_response["group"]["slug"] == group.slug


def test_membership_add_manager(client_query, groups, users):
    group = groups[0]
    user = users[0]

    response = client_query(
        """
        mutation addMembership($input: MembershipAddMutationInput!){
          addMembership(input: $input) {
            membership {
              id
              userRole
              user {
                email
              }
              group {
                slug
              }
            }
          }
        }
        """,
        variables={
            "input": {
                "userEmail": user.email,
                "groupSlug": group.slug,
                "userRole": Membership.ROLE_MANAGER,
            }
        },
    )
    membership = response.json()["data"]["addMembership"]["membership"]

    assert membership["id"]
    assert membership["user"]["email"] == user.email
    assert membership["group"]["slug"] == group.slug
    assert membership["userRole"] == Membership.ROLE_MANAGER.upper()


def test_membership_update(client_query, memberships):
    old_membership = memberships[0]

    assert old_membership.user_role != Membership.ROLE_MANAGER.upper()

    response = client_query(
        """
        mutation updateMembership($input: MembershipUpdateMutationInput!){
          updateMembership(input: $input) {
            membership {
              id
              userRole
              user {
                email
              }
              group {
                slug
              }
            }
          }
        }
        """,
        variables={
            "input": {
                "id": str(old_membership.id),
                "userRole": Membership.ROLE_MANAGER,
            }
        },
    )
    membership = response.json()["data"]["updateMembership"]["membership"]

    assert membership["id"]
    assert membership["user"]["email"] == old_membership.user.email
    assert membership["group"]["slug"] == old_membership.group.slug
    assert membership["userRole"] == Membership.ROLE_MANAGER.upper()


def test_membership_delete(settings, client_query, users, groups):
    member = users[0]
    manager = users[1]
    group = groups[0]

    old_membership = mixer.blend(Membership, user=member, group=group)
    mixer.blend(Membership, user=manager, group=group, user_role=Membership.ROLE_MANAGER)

    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

    client_query(
        """
        mutation deleteMembership($input: MembershipDeleteMutationInput!){
          deleteMembership(input: $input) {
            membership {
              user {
                email
              },
              group {
                slug
              }
            }
          }
        }
        """,
        variables={
            "input": {
                "id": str(old_membership.id),
            }
        },
    )

    assert not Membership.objects.filter(user=old_membership.user, group=old_membership.group)


def test_membership_delete_by_group_manager(settings, client_query, memberships, users):
    # This test tries to delete memberships[1], from user[1] with user[0] as
    # manager from membership group
    old_membership = memberships[1]
    manager = users[0]
    old_membership.group.add_manager(manager)

    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

    client_query(
        """
        mutation deleteMembership($input: MembershipDeleteMutationInput!){
          deleteMembership(input: $input) {
            membership {
              user {
                email
              },
              group {
                slug
              }
            }
          }
        }
        """,
        variables={
            "input": {
                "id": str(old_membership.id),
            }
        },
    )

    assert not Membership.objects.filter(user=old_membership.user, group=old_membership.group)


def test_membership_delete_by_any_other_user(settings, client_query, memberships):
    # Client query runs with user[0] from memberships[0]
    # This test tries to delete memberships[1], from user[1] with user[0]
    old_membership = memberships[1]

    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

    response = client_query(
        """
        mutation deleteMembership($input: MembershipDeleteMutationInput!){
          deleteMembership(input: $input) {
            membership {
              user {
                email
              },
              group {
                slug
              }
            }
          }
        }
        """,
        variables={
            "input": {
                "id": str(old_membership.id),
            }
        },
    )

    response = response.json()

    assert "errors" in response
    assert "has no permission to delete" in response["errors"][0]["message"]


def test_membership_delete_by_last_manager(settings, client_query, memberships, users):
    old_membership = memberships[0]

    settings.FEATURE_FLAGS["CHECK_PERMISSIONS"] = True

    response = client_query(
        """
        mutation deleteMembership($input: MembershipDeleteMutationInput!){
          deleteMembership(input: $input) {
            membership {
              user {
                email
              },
              group {
                slug
              }
            }
          }
        }
        """,
        variables={
            "input": {
                "id": str(old_membership.id),
            }
        },
    )

    response = response.json()

    assert "errors" in response
    assert "at least one manager" in response["errors"][0]["message"]
