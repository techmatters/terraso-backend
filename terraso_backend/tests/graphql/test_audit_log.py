
import pytest

from apps.audit_logs import services, api

pytestmark = pytest.mark.django_db



def test_audit_log_query(client_query, audit_log_user, audit_log_site_resource):

    logger = services.new_audit_logger()
    logger.log(user=audit_log_user, action=api.CREATE, resource=audit_log_site_resource)
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
    print(response)
    edges = response.json()["data"]["auditLogs"]["edges"]
    assert len(edges) == 1
    assert edges[0]["node"]["user"] == {"email": audit_log_user.email}

    logger.log(user=audit_log_user, action=api.CHANGE, resource=audit_log_site_resource)
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
    assert edges[0]["node"]["event"] == "A_1"

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
    assert edges[0]["node"]["event"] == "A_3"


