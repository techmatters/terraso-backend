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

pytestmark = pytest.mark.django_db


def test_shared_resource_update_by_source_works(client_query, data_entries):
    data_entry = data_entries[0]
    shared_resource = data_entry.shared_resources.all()[0]

    new_data = {
        "id": str(shared_resource.id),
        "shareAccess": "ALL",
    }
    response = client_query(
        """
        mutation updateSharedResource($input: SharedResourceUpdateMutationInput!) {
          updateSharedResource(input: $input) {
            sharedResource {
              id
              shareAccess
            }
          }
        }
        """,
        variables={"input": new_data},
    )
    json_result = response.json()
    print(json_result)
    result = json_result["data"]["updateSharedResource"]["sharedResource"]

    assert result == new_data


def test_shared_resource_update_by_non_creator_or_manager_fails_due_permission_check(
    client_query, data_entries, users
):
    data_entry = data_entries[0]
    shared_resource = data_entry.shared_resources.all()[0]

    # Let's force old data creator be different from client query user
    data_entry.created_by = users[2]
    data_entry.save()

    new_data = {
        "id": str(shared_resource.id),
        "shareAccess": "ALL",
    }

    response = client_query(
        """
        mutation updateSharedResource($input: SharedResourceUpdateMutationInput!) {
          updateSharedResource(input: $input) {
            errors
          }
        }
        """,
        variables={"input": new_data},
    )
    response = response.json()

    assert "errors" in response["data"]["updateSharedResource"]
    assert "update_not_allowed" in response["data"]["updateSharedResource"]["errors"][0]["message"]
