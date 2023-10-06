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

# import uuid
# from unittest import mock

import pytest

from apps.collaboration.models import Membership as CollaborationMembership
from apps.core import landscape_collaboration_roles

# from mixer.backend.django import mixer


pytestmark = pytest.mark.django_db


def test_landscape_membership_add(client_query, managed_landscapes, users):
    landscape = managed_landscapes[0]
    user = users[0]

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


# def test_landscape_membership_adding_duplicated_returns_previously_created(
#   client_query, managed_landscapes
# ):
#     landscape = managed_landscapes[0]
#     membership = landscape.membership_list.memberships.first()
#     user = membership.user

#     response = client_query(
#         """
#         mutation addMembership($input: LandscapeMembershipSaveMutationInput!){
#           saveLandscapeMembership(input: $input) {
#             membership {
#               id
#               userRole
#               user {
#                 email
#               }
#               group {
#                 slug
#               }
#             }
#           }
#         }
#         """,
#         variables={
#             "input": {
#                 "userEmail": user.email,
#                 "userRole"
#                 "landscapeSlug": landscape.slug,
#             }
#         },
#     )
#     membership_response = response.json()["data"]["addMembership"]["membership"]

#     assert membership_response["id"] == str(membership.id)
#     assert membership_response["userRole"] == membership.user_role.upper()
#     assert membership_response["user"]["email"] == user.email
#     assert membership_response["group"]["slug"] == group.slug


def test_landscape_membership_add_manager(client_query, managed_landscapes, users):
    landscape = managed_landscapes[0]
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


# def test_landscape_membership_add_manager_closed(client_query, groups_closed, users):
#     group = groups_closed[0]
#     user = users[0]

#     response = client_query(
#         """
#         mutation addMembership($input: LandscapeMembershipSaveMutationInput!){
#           saveLandscapeMembership(input: $input) {
#             membership {
#               id
#               userRole
#               membershipStatus
#               user {
#                 email
#               }
#               group {
#                 slug
#               }
#             }
#           }
#         }
#         """,
#         variables={
#             "input": {
#                 "userEmail": user.email,
#                 "groupSlug": group.slug,
#                 "userRole": Membership.ROLE_MANAGER,
#             }
#         },
#     )
#     membership = response.json()["data"]["addMembership"]["membership"]

#     assert membership["id"]
#     assert membership["user"]["email"] == user.email
#     assert membership["group"]["slug"] == group.slug
#     assert membership["userRole"] == Membership.ROLE_MANAGER.upper()
#     assert membership["membershipStatus"] == Membership.PENDING.upper()


# @mock.patch("apps.notifications.email.send_mail")
# def test_landscape_membership_add_member_closed_with_notification(
#     mocked_send_mail, client_query, groups_closed, users_with_group_notifications
# ):
#     group = groups_closed[0]
#     user = users_with_group_notifications[0]
#     other_user = users_with_group_notifications[1]

#     group.add_manager(other_user)

#     response = client_query(
#         """
#       mutation addMembership($input: LandscapeMembershipSaveMutationInput!){
#         saveLandscapeMembership(input: $input) {
#           membership {
#             id
#             userRole
#             membershipStatus
#             user {
#               email
#             }
#             group {
#               slug
#             }
#           }
#         }
#       }
#       """,
#         variables={
#             "input": {
#                 "userEmail": user.email,
#                 "groupSlug": group.slug,
#                 "userRole": Membership.ROLE_MEMBER,
#             }
#         },
#     )
#     membership = response.json()["data"]["addMembership"]["membership"]

#     mocked_send_mail.assert_called_once()
#     assert mocked_send_mail.call_args.args[3] == [other_user.name_and_email()]

#     assert membership["id"]
#     assert membership["user"]["email"] == user.email
#     assert membership["group"]["slug"] == group.slug
#     assert membership["userRole"] == Membership.ROLE_MEMBER.upper()
#     assert membership["membershipStatus"] == Membership.PENDING.upper()


# @mock.patch("apps.notifications.email.send_mail")
# def test_landscape_membership_add_member_closed_without_notification(
#     mocked_send_mail, client_query, groups_closed, users
# ):
#     group = groups_closed[0]
#     user = users[0]
#     other_user = users[1]

#     group.add_manager(other_user)

#     response = client_query(
#         """
#       mutation addMembership($input: LandscapeMembershipSaveMutationInput!){
#         saveLandscapeMembership(input: $input) {
#           membership {
#             id
#             userRole
#             membershipStatus
#             user {
#               email
#             }
#             group {
#               slug
#             }
#           }
#         }
#       }
#       """,
#         variables={
#             "input": {
#                 "userEmail": user.email,
#                 "groupSlug": group.slug,
#                 "userRole": Membership.ROLE_MEMBER,
#             }
#         },
#     )
#     membership = response.json()["data"]["addMembership"]["membership"]

#     mocked_send_mail.assert_not_called()

#     assert membership["id"]
#     assert membership["user"]["email"] == user.email
#     assert membership["group"]["slug"] == group.slug
#     assert membership["userRole"] == Membership.ROLE_MEMBER.upper()
#     assert membership["membershipStatus"] == Membership.PENDING.upper()


# @mock.patch("apps.notifications.email.send_mail")
# def test_landscape_membership_update(
#     mocked_send_mail, client_query, users, memberships_pending_with_notifications
# ):
#     user = users[0]
#     other_manager = users[1]
#     old_membership = memberships_pending_with_notifications[0]

#     old_membership.group.add_manager(user)
#     old_membership.group.add_manager(other_manager)

#     assert old_membership.user_role != Membership.ROLE_MANAGER.upper()
#     assert old_membership.membership_status != Membership.PENDING.upper()

#     response = client_query(
#         """
#       mutation updateMembership($input: MembershipUpdateMutationInput!){
#         updateMembership(input: $input) {
#           membership {
#             id
#             userRole
#             membershipStatus
#             user {
#               email
#             }
#             group {
#               slug
#             }
#           }
#         }
#       }
#       """,
#         variables={
#             "input": {
#                 "id": str(old_membership.id),
#                 "userRole": Membership.ROLE_MANAGER,
#                 "membershipStatus": Membership.APPROVED,
#             }
#         },
#     )
#     membership = response.json()["data"]["updateMembership"]["membership"]
#     mocked_send_mail.assert_called_once()
#     assert mocked_send_mail.call_args.args[3] == [old_membership.user.name_and_email()]

#     assert membership["id"]
#     assert membership["user"]["email"] == old_membership.user.email
#     assert membership["group"]["slug"] == old_membership.group.slug
#     assert membership["userRole"] == Membership.ROLE_MANAGER.upper()
#     assert membership["membershipStatus"] == Membership.APPROVED.upper()


# def test_landscape_membership_update_role_by_last_manager_fails(client_query, users, memberships):
#     user = users[0]
#     old_membership = memberships[0]

#     old_membership.group.add_manager(user)

#     assert old_membership.user_role != Membership.ROLE_MANAGER.upper()

#     response = client_query(
#         """
#         mutation updateMembership($input: MembershipUpdateMutationInput!){
#           updateMembership(input: $input) {
#             membership {
#               id
#               userRole
#               user {
#                 email
#               }
#               group {
#                 slug
#               }
#             }
#             errors
#           }
#         }
#         """,
#         variables={
#             "input": {
#                 "id": str(old_membership.id),
#                 "userRole": Membership.ROLE_MEMBER,
#             }
#         },
#     )
#     response = response.json()

#     assert "errors" in response["data"]["updateMembership"]
#     assert "update_not_allowed" in response["data"]["updateMembership"]["errors"][0]["message"]


# def test_landscape_membership_update_by_non_manager_fail(client_query, memberships):
#     old_membership = memberships[0]
#     old_membership.user_role = Membership.ROLE_MEMBER
#     old_membership.save()

#     response = client_query(
#         """
#         mutation updateMembership($input: MembershipUpdateMutationInput!){
#           updateMembership(input: $input) {
#             membership {
#               userRole
#             }
#             errors
#           }
#         }
#         """,
#         variables={
#             "input": {
#                 "id": str(old_membership.id),
#                 "userRole": Membership.ROLE_MANAGER,
#             }
#         },
#     )
#     response = response.json()

#     assert "errors" in response["data"]["updateMembership"]
#     assert "update_not_allowed" in response["data"]["updateMembership"]["errors"][0]["message"]


# def test_landscape_membership_update_not_found(client_query, memberships):
#     response = client_query(
#         """
#         mutation updateMembership($input: MembershipUpdateMutationInput!){
#           updateMembership(input: $input) {
#             membership {
#               userRole
#             }
#             errors
#           }
#         }
#         """,
#         variables={
#             "input": {
#                 "id": str(uuid.uuid4()),
#                 "userRole": Membership.ROLE_MANAGER,
#             }
#         },
#     )
#     response = response.json()

#     assert "errors" in response["data"]["updateMembership"]
#     assert "not_found" in response["data"]["updateMembership"]["errors"][0]["message"]


# def test_landscape_membership_delete(client_query, users, groups):
#     member = users[0]
#     manager = users[1]
#     group = groups[0]

#     old_membership = mixer.blend(Membership, user=member, group=group)
#     mixer.blend(Membership, user=manager, group=group, user_role=Membership.ROLE_MANAGER)

#     client_query(
#         """
#         mutation deleteMembership($input: MembershipDeleteMutationInput!){
#           deleteMembership(input: $input) {
#             membership {
#               user {
#                 email
#               },
#               group {
#                 slug
#               }
#             }
#           }
#         }
#         """,
#         variables={
#             "input": {
#                 "id": str(old_membership.id),
#             }
#         },
#     )

#     assert not Membership.objects.filter(user=old_membership.user, group=old_membership.group)


# def test_landscape_membership_soft_deleted_can_be_created_again(client_query, memberships):
#     old_membership = memberships[0]
#     old_membership.delete()

#     response = client_query(
#         """
#         mutation addMembership($input: LandscapeMembershipSaveMutationInput!){
#           saveLandscapeMembership(input: $input) {
#             membership {
#               id
#               userRole
#               user {
#                 email
#               }
#               group {
#                 slug
#               }
#             }
#           }
#         }
#         """,
#         variables={
#             "input": {
#                 "userEmail": old_membership.user.email,
#                 "groupSlug": old_membership.group.slug,
#             }
#         },
#     )
#     membership = response.json()["data"]["addMembership"]["membership"]

#     assert membership["id"]
#     assert membership["user"]["email"] == old_membership.user.email
#     assert membership["group"]["slug"] == old_membership.group.slug
#     assert membership["userRole"] == Membership.ROLE_MEMBER.upper()


# def test_landscape_membership_delete_by_group_manager(client_query, memberships, users):
#     # This test tries to delete memberships[1], from user[1] with user[0] as
#     # manager from membership group
#     old_membership = memberships[1]
#     manager = users[0]
#     old_membership.group.add_manager(manager)

#     client_query(
#         """
#         mutation deleteMembership($input: MembershipDeleteMutationInput!){
#           deleteMembership(input: $input) {
#             membership {
#               user {
#                 email
#               },
#               group {
#                 slug
#               }
#             }
#           }
#         }
#         """,
#         variables={
#             "input": {
#                 "id": str(old_membership.id),
#             }
#         },
#     )

#     assert not Membership.objects.filter(user=old_membership.user, group=old_membership.group)


# def test_landscape_membership_delete_by_any_other_user(client_query, memberships):
#     # Client query runs with user[0] from memberships[0]
#     # This test tries to delete memberships[1], from user[1] with user[0]
#     old_membership = memberships[1]

#     response = client_query(
#         """
#         mutation deleteMembership($input: MembershipDeleteMutationInput!){
#           deleteMembership(input: $input) {
#             membership {
#               user {
#                 email
#               },
#               group {
#                 slug
#               }
#             }
#             errors
#           }
#         }
#         """,
#         variables={
#             "input": {
#                 "id": str(old_membership.id),
#             }
#         },
#     )

#     response = response.json()

#     assert "errors" in response["data"]["deleteMembership"]
#     assert "delete_not_allowed" in response["data"]["deleteMembership"]["errors"][0]["message"]


# def test_landscape_membership_delete_by_last_manager(client_query, memberships, users):
#     old_membership = memberships[0]

#     response = client_query(
#         """
#         mutation deleteMembership($input: MembershipDeleteMutationInput!){
#           deleteMembership(input: $input) {
#             membership {
#               user {
#                 email
#               },
#               group {
#                 slug
#               }
#             }
#             errors
#           }
#         }
#         """,
#         variables={
#             "input": {
#                 "id": str(old_membership.id),
#             }
#         },
#     )

#     response = response.json()

#     assert "errors" in response["data"]["deleteMembership"]
#     assert "delete_not_allowed" in response["data"]["deleteMembership"]["errors"][0]["message"]
