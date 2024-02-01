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

from apps.audit_logs import api, services

pytestmark = pytest.mark.django_db


def test_audit_log_query(client_query, audit_log_user, site):
    logger = services.new_audit_logger()
    metadata = {"some_key": "some_value"}
    logger.log(user=audit_log_user, action=api.CREATE, resource=site, metadata=metadata)
    response = client_query(
        """
       {
            auditLogs {
                edges {
                    node {
                        clientTimestamp
                        resourceId
                        event
                        metadata
                        resourceContentType
                        user {
                           email
                        }

                    }
                }
            }
        }
        """,
    )
    expected_metadata = {
        "some_key": "some_value",
    }
    edges = response.json()["data"]["auditLogs"]["edges"]
    assert len(edges) == 1
    assert edges[0]["node"]["user"] == {"email": audit_log_user.email}
    assert edges[0]["node"]["resourceId"] == str(site.id)
    assert edges[0]["node"]["metadata"]["some_key"] == expected_metadata["some_key"]

    logger.log(user=audit_log_user, action=api.CHANGE, resource=site)
    response = client_query(
        """
       {
            auditLogs {
                edges {
                    node {
                        clientTimestamp
                        resourceId
                        event
                        metadata
                        resourceContentType
                        user {
                           email
                        }

                    }
                }
            }
        }
        """,
    )

    edges = response.json()["data"]["auditLogs"]["edges"]
    assert len(edges) == 2
    assert edges[0]["node"]["event"] == "CREATE"

    response = client_query(
        """
       {
            auditLogs(orderBy: "-clientTimestamp") {
                edges {
                    node {
                        clientTimestamp
                        resourceId
                        event
                        metadata
                        resourceContentType
                        user {
                           email
                        }

                    }
                }
            }
        }
        """,
    )

    edges = response.json()["data"]["auditLogs"]["edges"]
    assert len(edges) == 2
    assert edges[0]["node"]["event"] == "CHANGE"
