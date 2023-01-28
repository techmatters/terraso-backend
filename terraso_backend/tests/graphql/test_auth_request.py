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

import pytest

pytestmark = pytest.mark.django_db


def test_graphql_query_with_expired_token_returns_401_error_when_debug_is_off(
    settings, expired_client_query
):
    settings.DEBUG = False

    response = expired_client_query(
        """
        query {
            landscapes {
                edges {
                    node {
                        slug
                    }
                }
            }
        }
        """
    )
    assert response.status_code == 401
    assert "error" in response.json()


def test_graphql_query_with_expired_token_returns_not_ok_when_debug_is_on(
    settings, expired_client_query
):
    settings.DEBUG = True

    response = expired_client_query(
        """
        query {
            landscapes {
                edges {
                    node {
                        slug
                    }
                }
            }
        }
        """
    )
    assert response.status_code == 401
