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

import json
from urllib.parse import quote

import pytest

from apps.export.models import ExportToken

pytestmark = pytest.mark.django_db


class TestSiteExport:
    """Tests for single site export endpoints."""

    def test_export_site_csv(self, client, owned_site, site_export_token):
        """Test basic CSV export for a single site."""
        url = f"/export/token/site/{site_export_token.token}/test.csv"
        response = client.get(url)

        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        assert "attachment" in response["Content-Disposition"]

        content = response.content.decode("utf-8")
        assert "Site ID" in content  # CSV header
        assert str(owned_site.id) in content

    def test_export_site_json(self, client, owned_site, site_export_token):
        """Test JSON export for a single site."""
        url = f"/export/token/site/{site_export_token.token}/test.json"
        response = client.get(url)

        assert response.status_code == 200
        assert "application/json" in response["Content-Type"]
        assert "attachment" in response["Content-Disposition"]

        data = json.loads(response.content)
        assert "sites" in data
        assert len(data["sites"]) == 1
        assert data["sites"][0]["id"] == str(owned_site.id)

    def test_export_site_uses_database_name_for_filename(self, client, owned_site, site_export_token):
        """Test that Content-Disposition uses actual site name from database."""
        # Use a different name in URL than the actual site name
        url = f"/export/token/site/{site_export_token.token}/wrong_name.csv"
        response = client.get(url)

        assert response.status_code == 200
        # The filename should use the actual site name, not the URL name
        content_disposition = response["Content-Disposition"]
        assert owned_site.name in content_disposition or quote(owned_site.name) in content_disposition

    def test_export_site_html_page(self, client, owned_site, site_export_token):
        """Test HTML landing page for site export."""
        url = f"/export/token/site/{site_export_token.token}/test.html"
        response = client.get(url)

        assert response.status_code == 200
        assert "text/html" in response["Content-Type"]

        content = response.content.decode("utf-8")
        assert "Download CSV" in content
        assert "Download JSON" in content
        assert owned_site.name in content  # Display name from database


class TestProjectExport:
    """Tests for project export endpoints."""

    def test_export_project_csv(self, client, export_project, project_site, project_export_token):
        """Test CSV export for all sites in a project."""
        url = f"/export/token/project/{project_export_token.token}/test.csv"
        response = client.get(url)

        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"

        content = response.content.decode("utf-8")
        assert str(project_site.id) in content

    def test_export_project_json(self, client, export_project, project_site, project_export_token):
        """Test JSON export for all sites in a project."""
        url = f"/export/token/project/{project_export_token.token}/test.json"
        response = client.get(url)

        assert response.status_code == 200

        data = json.loads(response.content)
        assert "sites" in data
        assert len(data["sites"]) == 1
        assert data["sites"][0]["id"] == str(project_site.id)


class TestUserExport:
    """Tests for user-based export endpoints."""

    def test_export_user_owned_sites_csv(self, client, export_user, owned_site, user_export_token):
        """Test export of user's owned sites (not in projects)."""
        url = f"/export/token/user_owned/{user_export_token.token}/test.csv"
        response = client.get(url)

        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"

        content = response.content.decode("utf-8")
        assert str(owned_site.id) in content

    def test_export_user_all_sites_csv(
        self, client, export_user, owned_site, project_with_member, project_site, user_export_token
    ):
        """Test export of user's owned sites plus sites from projects they're a member of."""
        url = f"/export/token/user_all/{user_export_token.token}/test.csv"
        response = client.get(url)

        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"

        content = response.content.decode("utf-8")
        # Should include both owned site and project site
        assert str(owned_site.id) in content
        assert str(project_site.id) in content


class TestTokenValidation:
    """Tests for token validation and error handling."""

    def test_export_invalid_token_returns_404_page(self, client):
        """Test that invalid token returns the invalid token HTML page."""
        url = "/export/token/site/invalid-token-12345/test.csv"
        response = client.get(url)

        assert response.status_code == 404
        assert "text/html" in response["Content-Type"]

        content = response.content.decode("utf-8")
        assert "Export Link No Longer Valid" in content

    def test_export_wrong_token_type_returns_400(self, client, site_export_token):
        """Test that using a site token for project endpoint returns 400."""
        # site_export_token is for a SITE, but we're using it on project endpoint
        url = f"/export/token/project/{site_export_token.token}/test.csv"
        response = client.get(url)

        assert response.status_code == 400
        assert b"Invalid token type" in response.content

    def test_export_deleted_token_returns_404(self, client, owned_site, export_user):
        """Test that a deleted token returns 404."""
        token = ExportToken.create_token("SITE", str(owned_site.id), str(export_user.id))
        token_value = token.token

        # Delete the token
        token.delete()

        url = f"/export/token/site/{token_value}/test.csv"
        response = client.get(url)

        assert response.status_code == 404


class TestUnicodeHandling:
    """Tests for Unicode character handling in names."""

    def test_export_unicode_site_name(self, client, unicode_site, export_user):
        """Test export with Unicode characters in site name."""
        token = ExportToken.create_token("SITE", str(unicode_site.id), str(export_user.id))

        url = f"/export/token/site/{token.token}/test.csv"
        response = client.get(url)

        assert response.status_code == 200

        # Content-Disposition should have both filename* (UTF-8) and filename (ASCII fallback)
        content_disposition = response["Content-Disposition"]
        assert "filename*=UTF-8''" in content_disposition
        assert 'filename="' in content_disposition

    def test_export_html_page_displays_unicode_name(self, client, unicode_site, export_user):
        """Test that HTML page correctly displays Unicode site name."""
        token = ExportToken.create_token("SITE", str(unicode_site.id), str(export_user.id))

        url = f"/export/token/site/{token.token}/test.html"
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert unicode_site.name in content


class TestUnsupportedFormat:
    """Tests for unsupported format handling."""

    def test_export_unsupported_format_returns_400(self, client, site_export_token):
        """Test that unsupported format returns 400."""
        url = f"/export/token/site/{site_export_token.token}/test.xml"
        response = client.get(url)

        assert response.status_code == 400
        assert b"Unsupported format" in response.content


class TestRawFormat:
    """Tests for raw format query parameter."""

    def test_export_raw_format_returns_graphql_data(self, client, owned_site, site_export_token):
        """Test that ?format=raw returns raw GraphQL data without transformation."""
        url = f"/export/token/site/{site_export_token.token}/test.json?format=raw"
        response = client.get(url)

        assert response.status_code == 200
        assert "application/json" in response["Content-Type"]

        data = json.loads(response.content)
        assert "sites" in data
        assert len(data["sites"]) == 1
        # Raw format should have GraphQL structure (e.g., "site" wrapper from query)
        site_data = data["sites"][0]
        assert "id" in site_data

    def test_export_raw_format_only_supports_json(self, client, site_export_token):
        """Test that ?format=raw with CSV returns 400."""
        url = f"/export/token/site/{site_export_token.token}/test.csv?format=raw"
        response = client.get(url)

        assert response.status_code == 400
        assert b"Raw format only supports JSON" in response.content

    def test_export_raw_format_project(self, client, export_project, project_site, project_export_token):
        """Test raw format works for project exports."""
        url = f"/export/token/project/{project_export_token.token}/test.json?format=raw"
        response = client.get(url)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert "sites" in data
        assert len(data["sites"]) == 1
