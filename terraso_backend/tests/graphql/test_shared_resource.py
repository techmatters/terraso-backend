# Copyright © 2024 Technology Matters
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
from apps.core import group_collaboration_roles
from apps.core.models import SharedResource

pytestmark = pytest.mark.django_db


def test_shared_resource_access_no(client_query, data_entries):
    data_entry = data_entries[0]
    shared_resource = data_entry.shared_resources.all()[0]

    shared_resource.share_access = SharedResource.SHARE_ACCESS_NONE
    shared_resource.save()

    response = client_query(
        """
        {sharedResource(shareUuid: "%s") {
          shareAccess
        }}
        """
        % shared_resource.share_uuid
    )

    json_response = response.json()

    result = json_response["data"]["sharedResource"]

    assert result is None


def test_shared_resource_access_all(client_query, data_entries):
    data_entry = data_entries[0]
    shared_resource = data_entry.shared_resources.all()[0]

    shared_resource.target.membership_list.memberships.all().delete()

    shared_resource.share_access = SharedResource.SHARE_ACCESS_ALL
    shared_resource.save()

    response = client_query(
        """
        {sharedResource(shareUuid: "%s") {
          shareAccess
        }}
        """
        % shared_resource.share_uuid
    )

    json_response = response.json()

    result = json_response["data"]["sharedResource"]

    assert shared_resource.share_access == result["shareAccess"].lower()


def test_shared_resource_access_members(client_query, data_entries, users):
    data_entry = data_entries[0]
    shared_resource = data_entry.shared_resources.all()[0]

    shared_resource.target.membership_list.memberships.all().delete()

    shared_resource.target.membership_list.save_membership(
        users[0].email, group_collaboration_roles.ROLE_MEMBER, CollaborationMembership.APPROVED
    )

    shared_resource.share_access = SharedResource.SHARE_ACCESS_TARGET_MEMBERS
    shared_resource.save()

    response = client_query(
        """
        {sharedResource(shareUuid: "%s") {
          shareAccess
        }}
        """
        % shared_resource.share_uuid
    )

    json_response = response.json()

    result = json_response["data"]["sharedResource"]

    assert shared_resource.share_access == result["shareAccess"].lower()


def test_shared_resource_access_members_fail(client_query, data_entries, users):
    data_entry = data_entries[0]
    shared_resource = data_entry.shared_resources.all()[0]

    shared_resource.target.membership_list.memberships.all().delete()

    shared_resource.share_access = SharedResource.SHARE_ACCESS_TARGET_MEMBERS
    shared_resource.save()

    response = client_query(
        """
        {sharedResource(shareUuid: "%s") {
          shareAccess
        }}
        """
        % shared_resource.share_uuid
    )

    json_response = response.json()

    result = json_response["data"]["sharedResource"]

    assert result is None
