# Copyright © 2023 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.

import pytest

from apps.collaboration.models import Membership as CollaborationMembership
from apps.core import landscape_collaboration_roles

pytestmark = pytest.mark.django_db


def test_landscape_membership_add(client_query, managed_landscapes, users):
    landscape = managed_landscapes[0]
    user = users[0]

    landscape.membership_list.memberships.all().delete()

    response = client_query(
        """
        mutation addLandscapeMembership($input: LandscapeMembershipSaveMutationInput!){
          saveLandscapeMembership(input: $input) {
            memberships {
              id
              userRole
              user {
                email
              }
            }
            landscape {
              slug
            }
            errors
          }
        }
        """,
        variables={
            "input": {
                "userEmails": [user.email],
                "userRole": landscape_collaboration_roles.ROLE_MEMBER,
                "landscapeSlug": landscape.slug,
            }
        },
    )
    json_response = response.json()

    membership = json_response["data"]["saveLandscapeMembership"]["memberships"][0]

    assert membership["id"]
    assert membership["user"]["email"] == user.email
    assert membership["userRole"] == landscape_collaboration_roles.ROLE_MEMBER

    assert json_response["data"]["saveLandscapeMembership"]["landscape"]["slug"] == landscape.slug


def test_landscape_membership_add_landscape_not_found(client_query, users):
    user = users[0]

    response = client_query(
        """
        mutation addLandscapeMembership($input: LandscapeMembershipSaveMutationInput!){
          saveLandscapeMembership(input: $input) {
            errors
          }
        }
        """,
        variables={
            "input": {
                "userEmails": [user.email],
                "userRole": landscape_collaboration_roles.ROLE_MEMBER,
                "landscapeSlug": "non-existing-landscape",
            }
        },
    )
    response = response.json()

    assert "errors" in response["data"]["saveLandscapeMembership"]
    assert "not_found" in response["data"]["saveLandscapeMembership"]["errors"][0]["message"]


def test_landscape_membership_add_user_not_found(client_query, managed_landscapes):
    landscape = managed_landscapes[0]

    response = client_query(
        """
        mutation addLandscapeMembership($input: LandscapeMembershipSaveMutationInput!){
          saveLandscapeMembership(input: $input) {
            errors
          }
        }
        """,
        variables={
            "input": {
                "userEmails": ["no-existing@user.com"],
                "userRole": landscape_collaboration_roles.ROLE_MEMBER,
                "landscapeSlug": landscape.slug,
            }
        },
    )
    response = response.json()

    assert "errors" in response["data"]["saveLandscapeMembership"]
    assert (
        "update_not_allowed" in response["data"]["saveLandscapeMembership"]["errors"][0]["message"]
    )


def test_landscape_membership_adding_duplicated_returns_existing_membership(
    client_query, managed_landscapes, landscape_user_memberships
):
    landscape = managed_landscapes[0]
    membership = landscape_user_memberships[0]

    response = client_query(
        """
        mutation addMembership($input: LandscapeMembershipSaveMutationInput!){
          saveLandscapeMembership(input: $input) {
            memberships {
              id
              userRole
              user {
                email
              }
            }
          }
        }
        """,
        variables={
            "input": {
                "userEmails": [membership.user.email],
                "userRole": membership.user_role,
                "landscapeSlug": landscape.slug,
            }
        },
    )
    membership_response = response.json()["data"]["saveLandscapeMembership"]["memberships"][0]

    assert membership_response["id"] == str(membership.id)
    assert membership_response["userRole"] == membership.user_role
    assert membership_response["user"]["email"] == membership.user.email


def test_landscape_membership_add_manager(client_query, managed_landscapes, users):
    landscape = managed_landscapes[0]
    user = users[3]

    response = client_query(
        """
        mutation addMembership($input: LandscapeMembershipSaveMutationInput!){
          saveLandscapeMembership(input: $input) {
            memberships {
              id
              userRole
              membershipStatus
              user {
                email
              }
            }
          }
        }
        """,
        variables={
            "input": {
                "userEmails": [user.email],
                "landscapeSlug": landscape.slug,
                "userRole": landscape_collaboration_roles.ROLE_MANAGER,
            }
        },
    )
    json_response = response.json()
    membership = json_response["data"]["saveLandscapeMembership"]["memberships"][0]

    assert membership["id"]
    assert membership["user"]["email"] == user.email
    assert membership["userRole"] == landscape_collaboration_roles.ROLE_MANAGER
    assert membership["membershipStatus"] == CollaborationMembership.APPROVED.upper()


def test_landscape_membership_add_manager_fail(client_query, managed_landscapes, users):
    landscape = managed_landscapes[1]
    user = users[3]

    response = client_query(
        """
        mutation addMembership($input: LandscapeMembershipSaveMutationInput!){
          saveLandscapeMembership(input: $input) {
            memberships {
              id
            }
            errors
          }
        }
        """,
        variables={
            "input": {
                "userEmails": [user.email],
                "landscapeSlug": landscape.slug,
                "userRole": landscape_collaboration_roles.ROLE_MANAGER,
            }
        },
    )
    response = response.json()

    assert "errors" in response["data"]["saveLandscapeMembership"]
    assert (
        "update_not_allowed" in response["data"]["saveLandscapeMembership"]["errors"][0]["message"]
    )


def test_landscape_membership_join(client_query, managed_landscapes, users):
    landscape = managed_landscapes[1]
    user = users[0]

    response = client_query(
        """
        mutation addMembership($input: LandscapeMembershipSaveMutationInput!){
          saveLandscapeMembership(input: $input) {
            memberships {
              id
              userRole
              membershipStatus
              user {
                email
              }
            }
          }
        }
        """,
        variables={
            "input": {
                "userEmails": [user.email],
                "landscapeSlug": landscape.slug,
                "userRole": landscape_collaboration_roles.ROLE_MEMBER,
            }
        },
    )
    json_response = response.json()
    membership = json_response["data"]["saveLandscapeMembership"]["memberships"][0]

    assert membership["id"]
    assert membership["user"]["email"] == user.email
    assert membership["userRole"] == landscape_collaboration_roles.ROLE_MEMBER
    assert membership["membershipStatus"] == CollaborationMembership.APPROVED.upper()


def test_landscape_membership_update(client_query, managed_landscapes, landscape_user_memberships):
    landscape = managed_landscapes[0]
    old_membership = landscape_user_memberships[0]

    assert old_membership.user_role != landscape_collaboration_roles.ROLE_MANAGER

    response = client_query(
        """
      mutation updateMembership($input: LandscapeMembershipSaveMutationInput!){
        saveLandscapeMembership(input: $input) {
          memberships {
            id
            userRole
            membershipStatus
            user {
              email
            }
          }
          landscape {
            slug
          }
        }
      }
      """,
        variables={
            "input": {
                "landscapeSlug": old_membership.membership_list.landscape.get().slug,
                "userEmails": [old_membership.user.email],
                "userRole": landscape_collaboration_roles.ROLE_MANAGER,
            }
        },
    )
    json_response = response.json()

    assert json_response["data"]["saveLandscapeMembership"]["landscape"]["slug"] == landscape.slug

    membership = json_response["data"]["saveLandscapeMembership"]["memberships"][0]

    assert membership["id"]
    assert membership["user"]["email"] == old_membership.user.email
    assert membership["userRole"] == landscape_collaboration_roles.ROLE_MANAGER
    assert membership["membershipStatus"] == CollaborationMembership.APPROVED.upper()


def test_landscape_membership_update_by_non_manager_fail(
    client_query, users, managed_landscapes, landscape_user_memberships
):
    current_manager = users[0]
    landscape = managed_landscapes[0]

    membership = landscape_user_memberships[0]

    landscape.membership_list.save_membership(
        current_manager.email,
        landscape_collaboration_roles.ROLE_MEMBER,
        CollaborationMembership.APPROVED,
    )

    response = client_query(
        """
        mutation updateMembership($input: LandscapeMembershipSaveMutationInput!){
          saveLandscapeMembership(input: $input) {
            memberships {
              id
              userRole
              user {
                email
              }
            }
            errors
          }
        }
        """,
        variables={
            "input": {
                "landscapeSlug": landscape.slug,
                "userEmails": [membership.user.email],
                "userRole": landscape_collaboration_roles.ROLE_MEMBER,
            }
        },
    )
    response = response.json()

    assert "errors" in response["data"]["saveLandscapeMembership"]
    assert (
        "update_not_allowed" in response["data"]["saveLandscapeMembership"]["errors"][0]["message"]
    )


def test_landscape_membership_update_not_found(client_query, managed_landscapes):
    response = client_query(
        """
        mutation updateMembership($input: LandscapeMembershipSaveMutationInput!){
          saveLandscapeMembership(input: $input) {
            memberships {
              userRole
            }
            errors
          }
        }
        """,
        variables={
            "input": {
                "landscapeSlug": "non-existing-landscape",
                "userEmails": ["useremail@test.com"],
                "userRole": landscape_collaboration_roles.ROLE_MANAGER,
            }
        },
    )
    response = response.json()

    assert "errors" in response["data"]["saveLandscapeMembership"]
    assert "not_found" in response["data"]["saveLandscapeMembership"]["errors"][0]["message"]


def test_landscape_membership_delete(client_query, managed_landscapes, landscape_user_memberships):
    landscape = managed_landscapes[0]
    old_membership = landscape_user_memberships[0]

    assert CollaborationMembership.objects.filter(
        user=old_membership.user, membership_list__landscape=landscape
    )

    client_query(
        """
        mutation deleteMembership($input: LandscapeMembershipDeleteMutationInput!){
          deleteLandscapeMembership(input: $input) {
            membership {
              user {
                email
              },
            }
          }
        }
        """,
        variables={
            "input": {
                "landscapeSlug": landscape.slug,
                "id": str(old_membership.id),
            }
        },
    )

    assert not CollaborationMembership.objects.filter(
        user=old_membership.user, membership_list__landscape=landscape
    )


def test_landscape_membership_soft_deleted_can_be_created_again(
    client_query, landscape_user_memberships, managed_landscapes
):
    landscape = managed_landscapes[0]
    old_membership = landscape_user_memberships[0]
    old_membership.delete()

    assert not landscape.membership_list.memberships.filter(
        user=old_membership.user, deleted_at=None
    ).exists()

    response = client_query(
        """
        mutation addMembership($input: LandscapeMembershipSaveMutationInput!){
          saveLandscapeMembership(input: $input) {
            memberships {
              id
              userRole
              user {
                email
              }
            }
          }
        }
        """,
        variables={
            "input": {
                "userEmails": [old_membership.user.email],
                "landscapeSlug": landscape.slug,
                "userRole": landscape_collaboration_roles.ROLE_MEMBER,
            }
        },
    )
    membership = response.json()["data"]["saveLandscapeMembership"]["memberships"][0]

    assert membership["id"]
    assert membership["user"]["email"] == old_membership.user.email
    assert membership["userRole"] == landscape_collaboration_roles.ROLE_MEMBER
    assert landscape.membership_list.memberships.filter(
        user=old_membership.user, deleted_at=None
    ).exists()


def test_landscape_membership_delete_by_membership_owner(client_query, users, managed_landscapes):
    landscape = managed_landscapes[0]
    old_membership = landscape.membership_list.memberships.filter(
        user=users[0], deleted_at=None
    ).first()

    old_membership.user_role = landscape_collaboration_roles.ROLE_MEMBER
    old_membership.save()

    client_query(
        """
        mutation deleteMembership($input: LandscapeMembershipDeleteMutationInput!){
          deleteLandscapeMembership(input: $input) {
            membership {
              user {
                email
              },
            }
          }
        }
        """,
        variables={
            "input": {
                "id": str(old_membership.id),
                "landscapeSlug": landscape.slug,
            }
        },
    )

    assert not CollaborationMembership.objects.filter(
        user=old_membership.user, membership_list__landscape=landscape
    )


def test_landscape_membership_delete_by_any_other_user(
    client_query, landscape_user_memberships, managed_landscapes
):
    old_membership = landscape_user_memberships[1]
    landscape = managed_landscapes[1]

    response = client_query(
        """
        mutation deleteMembership($input: LandscapeMembershipDeleteMutationInput!){
          deleteLandscapeMembership(input: $input) {
            membership {
              user {
                email
              },
            }
            errors
          }
        }
        """,
        variables={
            "input": {
                "id": str(old_membership.id),
                "landscapeSlug": landscape.slug,
            }
        },
    )

    response = response.json()

    assert "errors" in response["data"]["deleteLandscapeMembership"]
    assert (
        "delete_not_allowed"
        in response["data"]["deleteLandscapeMembership"]["errors"][0]["message"]
    )


def test_landscape_membership_delete_by_last_manager(client_query, managed_landscapes, users):
    landscape = managed_landscapes[0]
    manager_membership = landscape.membership_list.memberships.by_role(
        landscape_collaboration_roles.ROLE_MANAGER,
    ).first()

    response = client_query(
        """
        mutation deleteMembership($input: LandscapeMembershipDeleteMutationInput!){
          deleteLandscapeMembership(input: $input) {
            membership {
              user {
                email
              },
            }
            errors
          }
        }
        """,
        variables={
            "input": {
                "id": str(manager_membership.id),
                "landscapeSlug": landscape.slug,
            }
        },
    )

    response = response.json()

    assert "errors" in response["data"]["deleteLandscapeMembership"]
    assert (
        "delete_not_allowed"
        in response["data"]["deleteLandscapeMembership"]["errors"][0]["message"]
    )
    assert "manager_count" in response["data"]["deleteLandscapeMembership"]["errors"][0]["message"]
