import pytest

pytestmark = pytest.mark.django_db


def test_graphql_query_with_expired_token_returns_401_error(expired_client_query):
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
