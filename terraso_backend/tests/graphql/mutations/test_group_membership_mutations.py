# Copyright © 2021-2023 Technology Matters
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

import uuid
from unittest import mock

import pytest
from mixer.backend.django import mixer

from apps.collaboration.models import Membership as CollaborationMembership
from apps.core import group_collaboration_roles

pytestmark = pytest.mark.django_db


def test_group_membership_add(client_query, groups, users):
    group = groups[0]
    user = users[0]

    response = client_query(
        """
        mutation addMembership($input: GroupMembershipSaveMutationInput!){
          saveGroupMembership(input: $input) {
            memberships {
              id
              userRole
              user {
                email
              }
            }
            group {
              slug
            }
          }
        }
        """,
        variables={
            "input": {
                "userEmails": [user.email],
                "groupSlug": group.slug,
                "userRole": group_collaboration_roles.ROLE_MEMBER,
            }
        },
    )
    json_response = response.json()
    membership = json_response["data"]["saveGroupMembership"]["memberships"][0]

    assert membership["id"]
    assert membership["user"]["email"] == user.email
    assert membership["userRole"] == group_collaboration_roles.ROLE_MEMBER

    assert json_response["data"]["saveGroupMembership"]["group"]["slug"] == group.slug


def test_group_membership_add_group_not_found(client_query, users):
    user = users[0]

    response = client_query(
        """
        mutation addMembership($input: GroupMembershipSaveMutationInput!){
          saveGroupMembership(input: $input) {
            memberships {
              id
              userRole
              user {
                email
              }
              
            }
            group {
              slug
            }
            errors
          }
        }
        """,
        variables={
            "input": {
                "userEmails": [user.email],
                "groupSlug": "non-existing-group",
                "userRole": group_collaboration_roles.ROLE_MEMBER,
            }
        },
    )
    response = response.json()

    assert "errors" in response["data"]["saveGroupMembership"]
    assert "not_found" in response["data"]["saveGroupMembership"]["errors"][0]["message"]


def test_group_membership_add_user_not_found(client_query, groups):
    group = groups[0]

    response = client_query(
        """
        mutation addMembership($input: GroupMembershipSaveMutationInput!){
          saveGroupMembership(input: $input) {
            memberships {
              id
              userRole
              user {
                email
              }
              
            }
            group {
              slug
            }
            errors
          }
        }
        """,
        variables={
            "input": {
                "userEmails": ["no-existing@user.com"],
                "groupSlug": group.slug,
                "userRole": group_collaboration_roles.ROLE_MEMBER,
            }
        },
    )
    response = response.json()

    assert "errors" in response["data"]["saveGroupMembership"]
    assert "update_not_allowed" in response["data"]["saveGroupMembership"]["errors"][0]["message"]


def test_group_membership_adding_duplicated_returns_previously_created(
    client_query, group_manager_memberships, groups
):
    membership = group_manager_memberships[0]
    group = groups[0]
    user = membership.user

    response = client_query(
        """
        mutation addMembership($input: GroupMembershipSaveMutationInput!){
          saveGroupMembership(input: $input) {
            memberships {
              id
              userRole
              user {
                email
              }
            }
            group {
              slug
            }
          }
        }
        """,
        variables={
            "input": {
                "userEmails": [user.email],
                "groupSlug": group.slug,
                "userRole": group_collaboration_roles.ROLE_MANAGER,
            }
        },
    )

    membership_response = response.json()["data"]["saveGroupMembership"]["memberships"][0]

    assert membership_response["id"] == str(membership.id)
    assert membership_response["userRole"] == membership.user_role
    assert membership_response["user"]["email"] == user.email


def test_group_membership_add_manager_opened(
    client_query, groups, users, group_manager_memberships
):
    group = groups[0]
    user = users[0]

    response = client_query(
        """
        mutation addMembership($input: GroupMembershipSaveMutationInput!){
          saveGroupMembership(input: $input) {
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
                "groupSlug": group.slug,
                "userRole": group_collaboration_roles.ROLE_MANAGER,
            }
        },
    )
    json_response = response.json()
    membership = json_response["data"]["saveGroupMembership"]["memberships"][0]

    assert membership["id"]
    assert membership["user"]["email"] == user.email
    assert membership["userRole"] == group_collaboration_roles.ROLE_MANAGER
    assert membership["membershipStatus"] == CollaborationMembership.APPROVED.upper()


def test_group_membership_add_manager_closed(
    client_query, groups_closed, groups_closed_managers, users
):
    group = groups_closed[0]
    user = users[1]

    response = client_query(
        """
        mutation addMembership($input: GroupMembershipSaveMutationInput!){
          saveGroupMembership(input: $input) {
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
                "groupSlug": group.slug,
                "userRole": group_collaboration_roles.ROLE_MANAGER,
            }
        },
    )
    membership = response.json()["data"]["saveGroupMembership"]["memberships"][0]

    assert membership["id"]
    assert membership["user"]["email"] == user.email
    assert membership["userRole"] == group_collaboration_roles.ROLE_MANAGER
    assert membership["membershipStatus"] == CollaborationMembership.PENDING.upper()


@mock.patch("apps.notifications.email.send_mail")
def test_group_membership_add_member_closed_with_notification(
    mocked_send_mail,
    client_query,
    groups_closed,
    groups_closed_managers,
    users_with_group_notifications,
):
    group = groups_closed[0]
    user = users_with_group_notifications[0]
    other_user = users_with_group_notifications[1]

    group.add_manager(other_user)

    response = client_query(
        """
      mutation addMembership($input: GroupMembershipSaveMutationInput!){
        saveGroupMembership(input: $input) {
          memberships {
            id
            userRole
            membershipStatus
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
                "userEmails": [user.email],
                "groupSlug": group.slug,
                "userRole": group_collaboration_roles.ROLE_MEMBER,
            }
        },
    )
    json_response = response.json()
    membership = json_response["data"]["saveGroupMembership"]["memberships"][0]

    mocked_send_mail.assert_called_once()
    assert mocked_send_mail.call_args.args[3] == [other_user.name_and_email()]

    assert membership["id"]
    assert membership["user"]["email"] == user.email
    assert membership["userRole"] == group_collaboration_roles.ROLE_MEMBER
    assert membership["membershipStatus"] == CollaborationMembership.PENDING.upper()


@mock.patch("apps.notifications.email.send_mail")
def test_group_membership_add_member_closed_without_notification(
    mocked_send_mail, client_query, groups_closed, groups_closed_managers, users
):
    group = groups_closed[0]
    user = users[0]
    other_user = users[1]

    group.add_manager(other_user)

    response = client_query(
        """
      mutation addMembership($input: GroupMembershipSaveMutationInput!){
        saveGroupMembership(input: $input) {
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
                "groupSlug": group.slug,
                "userRole": group_collaboration_roles.ROLE_MEMBER,
            }
        },
    )
    membership = response.json()["data"]["saveGroupMembership"]["memberships"][0]

    mocked_send_mail.assert_not_called()

    assert membership["id"]
    assert membership["user"]["email"] == user.email
    assert membership["userRole"] == group_collaboration_roles.ROLE_MEMBER
    assert membership["membershipStatus"] == CollaborationMembership.PENDING.upper()


@mock.patch("apps.notifications.email.send_mail")
def test_group_membership_update(
    mocked_send_mail, client_query, users, memberships_pending_with_notifications
):
    user = users[0]
    other_manager = users[1]
    old_membership = memberships_pending_with_notifications[0]

    old_membership.group.add_manager(user)
    old_membership.group.add_manager(other_manager)

    assert old_membership.user_role != group_collaboration_roles.ROLE_MANAGER
    assert old_membership.membership_status != CollaborationMembership.PENDING.upper()

    response = client_query(
        """
      mutation updateMembership($input: MembershipUpdateMutationInput!){
        updateMembership(input: $input) {
          membership {
            id
            userRole
            membershipStatus
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
                "userRole": group_collaboration_roles.ROLE_MANAGER,
                "membershipStatus": CollaborationMembership.APPROVED,
            }
        },
    )
    membership = response.json()["data"]["updateMembership"]["membership"]
    mocked_send_mail.assert_called_once()
    assert mocked_send_mail.call_args.args[3] == [old_membership.user.name_and_email()]

    assert membership["id"]
    assert membership["user"]["email"] == old_membership.user.email
    assert membership["group"]["slug"] == old_membership.group.slug
    assert membership["userRole"] == group_collaboration_roles.ROLE_MANAGER
    assert membership["membershipStatus"] == CollaborationMembership.APPROVED.upper()


def test_group_membership_update_role_by_last_manager_fails(client_query, users, memberships):
    user = users[0]
    old_membership = memberships[0]

    old_membership.group.add_manager(user)

    assert old_membership.user_role != group_collaboration_roles.ROLE_MANAGER

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
            errors
          }
        }
        """,
        variables={
            "input": {
                "id": str(old_membership.id),
                "userRole": group_collaboration_roles.ROLE_MEMBER,
            }
        },
    )
    response = response.json()

    assert "errors" in response["data"]["updateMembership"]
    assert "update_not_allowed" in response["data"]["updateMembership"]["errors"][0]["message"]


def test_group_membership_update_by_non_manager_fail(client_query, memberships):
    old_membership = memberships[0]
    old_membership.user_role = group_collaboration_roles.ROLE_MEMBER
    old_membership.save()

    response = client_query(
        """
        mutation updateMembership($input: MembershipUpdateMutationInput!){
          updateMembership(input: $input) {
            membership {
              userRole
            }
            errors
          }
        }
        """,
        variables={
            "input": {
                "id": str(old_membership.id),
                "userRole": group_collaboration_roles.ROLE_MANAGER,
            }
        },
    )
    response = response.json()

    assert "errors" in response["data"]["updateMembership"]
    assert "update_not_allowed" in response["data"]["updateMembership"]["errors"][0]["message"]


def test_group_membership_update_not_found(client_query, memberships):
    response = client_query(
        """
        mutation updateMembership($input: MembershipUpdateMutationInput!){
          updateMembership(input: $input) {
            membership {
              userRole
            }
            errors
          }
        }
        """,
        variables={
            "input": {
                "id": str(uuid.uuid4()),
                "userRole": group_collaboration_roles.ROLE_MANAGER,
            }
        },
    )
    response = response.json()

    assert "errors" in response["data"]["updateMembership"]
    assert "not_found" in response["data"]["updateMembership"]["errors"][0]["message"]


def test_group_membership_delete(client_query, users, groups):
    member = users[0]
    manager = users[1]
    group = groups[0]

    old_membership = mixer.blend(
        CollaborationMembership, user=member, membership_list=group.membership_list
    )
    mixer.blend(
        CollaborationMembership,
        user=manager,
        group=group,
        user_role=group_collaboration_roles.ROLE_MANAGER,
    )

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

    assert not CollaborationMembership.objects.filter(
        user=old_membership.user, membership_list=old_membership.group.membership_list
    )


def test_group_membership_soft_deleted_can_be_created_again(client_query, memberships):
    old_membership = memberships[0]
    old_membership.delete()

    response = client_query(
        """
        mutation addMembership($input: GroupMembershipSaveMutationInput!){
          saveGroupMembership(input: $input) {
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
                "userEmail": old_membership.user.email,
                "groupSlug": old_membership.group.slug,
            }
        },
    )
    membership = response.json()["data"]["saveGroupMembership"]["membership"]

    assert membership["id"]
    assert membership["user"]["email"] == old_membership.user.email
    assert membership["group"]["slug"] == old_membership.group.slug
    assert membership["userRole"] == group_collaboration_roles.ROLE_MEMBER


def test_group_membership_delete_by_group_manager(client_query, memberships, users):
    # This test tries to delete memberships[1], from user[1] with user[0] as
    # manager from membership group
    old_membership = memberships[1]
    manager = users[0]
    old_membership.group.add_manager(manager)

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

    assert not CollaborationMembership.objects.filter(
        user=old_membership.user, membership_list=old_membership.group.membership_list
    )


def test_group_membership_delete_by_any_other_user(client_query, memberships):
    # Client query runs with user[0] from memberships[0]
    # This test tries to delete memberships[1], from user[1] with user[0]
    old_membership = memberships[1]

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
            errors
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

    assert "errors" in response["data"]["deleteMembership"]
    assert "delete_not_allowed" in response["data"]["deleteMembership"]["errors"][0]["message"]


def test_group_membership_delete_by_last_manager(client_query, memberships, users):
    old_membership = memberships[0]

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
            errors
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

    assert "errors" in response["data"]["deleteMembership"]
    assert "delete_not_allowed" in response["data"]["deleteMembership"]["errors"][0]["message"]
