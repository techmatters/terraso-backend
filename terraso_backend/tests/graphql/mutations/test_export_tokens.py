# Copyright © 2021-2025 Technology Matters
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

"""Tests for export token GraphQL mutations and queries."""

import json

import pytest
from mixer.backend.django import mixer

from apps.export.models import ExportToken
from apps.project_management.models import Project, Site

pytestmark = pytest.mark.django_db


# Fixtures
# Note: These fixtures use `user` from tests/graphql/conftest.py (the authenticated
# GraphQL user). Similar fixtures exist in tests/export/conftest.py which use
# `export_user` (users[0]) for HTTP export endpoint tests.


@pytest.fixture
def user_site(user):
    """Site owned by the authenticated user."""
    return mixer.blend(Site, owner=user, name="User's Site")


@pytest.fixture
def other_user_site(users):
    """Site owned by another user."""
    return mixer.blend(Site, owner=users[1], name="Other User's Site")


@pytest.fixture
def user_project(user):
    """Project where the authenticated user is a manager."""
    project = mixer.blend(Project, name="User's Project")
    project.add_manager(user)
    return project


@pytest.fixture
def other_user_project(users):
    """Project where the authenticated user has no access."""
    project = mixer.blend(Project, name="Other User's Project")
    project.add_manager(users[1])
    return project


# GraphQL Queries and Mutations


ADD_EXPORT_TOKEN = """
mutation addExportToken($resourceType: ResourceTypeEnum!, $resourceId: ID!) {
  addExportToken(resourceType: $resourceType, resourceId: $resourceId) {
    tokens {
      token
      resourceType
      resourceId
    }
  }
}
"""

DELETE_EXPORT_TOKEN = """
mutation deleteExportToken($token: String!) {
  deleteExportToken(token: $token) {
    tokens {
      token
      resourceType
      resourceId
    }
  }
}
"""

ALL_EXPORT_TOKENS_QUERY = """
query allExportTokens {
  allExportTokens {
    token
    resourceType
    resourceId
  }
}
"""


# Tests for addExportToken mutation


class TestAddExportToken:
    """Tests for the addExportToken mutation."""

    def test_add_site_token_success(self, client_query, user, user_site):
        """User can create export token for their own site."""
        response = client_query(
            ADD_EXPORT_TOKEN,
            variables={"resourceType": "SITE", "resourceId": str(user_site.id)},
        )
        content = json.loads(response.content)

        assert "errors" not in content, content.get("errors")
        tokens = content["data"]["addExportToken"]["tokens"]
        assert len(tokens) == 1
        assert tokens[0]["resourceType"] == "SITE"
        assert tokens[0]["resourceId"] == str(user_site.id)

        # Verify token was created in database
        assert ExportToken.objects.filter(
            resource_type="SITE",
            resource_id=str(user_site.id),
            user_id=str(user.id),
        ).exists()

    def test_add_project_token_success(self, client_query, user, user_project):
        """User can create export token for a project they manage."""
        response = client_query(
            ADD_EXPORT_TOKEN,
            variables={"resourceType": "PROJECT", "resourceId": str(user_project.id)},
        )
        content = json.loads(response.content)

        assert "errors" not in content, content.get("errors")
        tokens = content["data"]["addExportToken"]["tokens"]
        assert len(tokens) == 1
        assert tokens[0]["resourceType"] == "PROJECT"
        assert tokens[0]["resourceId"] == str(user_project.id)

    def test_add_user_token_success(self, client_query, user):
        """User can create export token for themselves."""
        response = client_query(
            ADD_EXPORT_TOKEN,
            variables={"resourceType": "USER", "resourceId": str(user.id)},
        )
        content = json.loads(response.content)

        assert "errors" not in content, content.get("errors")
        tokens = content["data"]["addExportToken"]["tokens"]
        assert len(tokens) == 1
        assert tokens[0]["resourceType"] == "USER"
        assert tokens[0]["resourceId"] == str(user.id)

    def test_add_token_idempotent(self, client_query, user, user_site):
        """Creating the same token twice returns the existing token."""
        # Create first token
        response1 = client_query(
            ADD_EXPORT_TOKEN,
            variables={"resourceType": "SITE", "resourceId": str(user_site.id)},
        )
        content1 = json.loads(response1.content)
        token1 = content1["data"]["addExportToken"]["tokens"][0]["token"]

        # Create second token - should return the same one
        response2 = client_query(
            ADD_EXPORT_TOKEN,
            variables={"resourceType": "SITE", "resourceId": str(user_site.id)},
        )
        content2 = json.loads(response2.content)
        token2 = content2["data"]["addExportToken"]["tokens"][0]["token"]

        assert token1 == token2
        assert ExportToken.objects.filter(resource_id=str(user_site.id)).count() == 1

    def test_add_token_unauthorized_site(self, client_query, other_user_site):
        """User cannot create export token for another user's site."""
        response = client_query(
            ADD_EXPORT_TOKEN,
            variables={"resourceType": "SITE", "resourceId": str(other_user_site.id)},
        )
        content = json.loads(response.content)

        assert "errors" in content
        assert "permission" in content["errors"][0]["message"].lower()

    def test_add_token_unauthorized_project(self, client_query, other_user_project):
        """User cannot create export token for a project they don't have access to."""
        response = client_query(
            ADD_EXPORT_TOKEN,
            variables={"resourceType": "PROJECT", "resourceId": str(other_user_project.id)},
        )
        content = json.loads(response.content)

        assert "errors" in content
        assert "permission" in content["errors"][0]["message"].lower()

    def test_add_token_unauthorized_user(self, client_query, users):
        """User cannot create export token for another user."""
        other_user = users[1]
        response = client_query(
            ADD_EXPORT_TOKEN,
            variables={"resourceType": "USER", "resourceId": str(other_user.id)},
        )
        content = json.loads(response.content)

        assert "errors" in content
        assert "permission" in content["errors"][0]["message"].lower()

    def test_add_token_nonexistent_site(self, client_query):
        """Error when creating token for nonexistent site."""
        response = client_query(
            ADD_EXPORT_TOKEN,
            variables={"resourceType": "SITE", "resourceId": "00000000-0000-0000-0000-000000000000"},
        )
        content = json.loads(response.content)

        assert "errors" in content
        assert "not found" in content["errors"][0]["message"].lower()


# Tests for deleteExportToken mutation


class TestDeleteExportToken:
    """Tests for the deleteExportToken mutation."""

    def test_delete_token_success(self, client_query, user, user_site):
        """User can delete their own export token."""
        # Create a token first
        token = ExportToken.create_token("SITE", str(user_site.id), str(user.id))
        token_value = token.token

        response = client_query(DELETE_EXPORT_TOKEN, variables={"token": token_value})
        content = json.loads(response.content)

        assert "errors" not in content, content.get("errors")
        # Verify token was deleted
        assert not ExportToken.objects.filter(token=token_value).exists()

    def test_delete_token_returns_remaining_tokens(self, client_query, user, user_site, user_project):
        """After deletion, returns list of remaining tokens."""
        # Create two tokens
        site_token = ExportToken.create_token("SITE", str(user_site.id), str(user.id))
        project_token = ExportToken.create_token("PROJECT", str(user_project.id), str(user.id))

        # Delete the site token
        response = client_query(DELETE_EXPORT_TOKEN, variables={"token": site_token.token})
        content = json.loads(response.content)

        assert "errors" not in content, content.get("errors")
        tokens = content["data"]["deleteExportToken"]["tokens"]
        assert len(tokens) == 1
        assert tokens[0]["token"] == project_token.token

    def test_delete_token_unauthorized(self, client_query, user, users, other_user_site):
        """User cannot delete another user's token."""
        other_user = users[1]
        token = ExportToken.create_token("SITE", str(other_user_site.id), str(other_user.id))

        response = client_query(DELETE_EXPORT_TOKEN, variables={"token": token.token})
        content = json.loads(response.content)

        assert "errors" in content
        assert "permission" in content["errors"][0]["message"].lower()
        # Verify token still exists
        assert ExportToken.objects.filter(token=token.token).exists()

    def test_delete_nonexistent_token(self, client_query):
        """Error when deleting nonexistent token."""
        response = client_query(
            DELETE_EXPORT_TOKEN, variables={"token": "nonexistent-token-value"}
        )
        content = json.loads(response.content)

        assert "errors" in content
        assert "not found" in content["errors"][0]["message"].lower()


# Tests for allExportTokens query


class TestAllExportTokensQuery:
    """Tests for the allExportTokens query."""

    def test_query_all_tokens(self, client_query, user, user_site, user_project):
        """User can list all their export tokens."""
        site_token = ExportToken.create_token("SITE", str(user_site.id), str(user.id))
        project_token = ExportToken.create_token("PROJECT", str(user_project.id), str(user.id))
        user_token = ExportToken.create_token("USER", str(user.id), str(user.id))

        response = client_query(ALL_EXPORT_TOKENS_QUERY)
        content = json.loads(response.content)

        assert "errors" not in content, content.get("errors")
        tokens = content["data"]["allExportTokens"]
        assert len(tokens) == 3

        token_values = {t["token"] for t in tokens}
        assert site_token.token in token_values
        assert project_token.token in token_values
        assert user_token.token in token_values

    def test_query_empty_tokens(self, client_query):
        """Returns empty list when user has no tokens."""
        response = client_query(ALL_EXPORT_TOKENS_QUERY)
        content = json.loads(response.content)

        assert "errors" not in content, content.get("errors")
        assert content["data"]["allExportTokens"] == []

    def test_query_only_returns_own_tokens(self, client_query, user, users, user_site, other_user_site):
        """User only sees their own tokens, not other users' tokens."""
        other_user = users[1]
        user_token = ExportToken.create_token("SITE", str(user_site.id), str(user.id))
        ExportToken.create_token("SITE", str(other_user_site.id), str(other_user.id))

        response = client_query(ALL_EXPORT_TOKENS_QUERY)
        content = json.loads(response.content)

        assert "errors" not in content, content.get("errors")
        tokens = content["data"]["allExportTokens"]
        assert len(tokens) == 1
        assert tokens[0]["token"] == user_token.token
