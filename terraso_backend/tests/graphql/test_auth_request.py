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
