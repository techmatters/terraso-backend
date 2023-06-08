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
