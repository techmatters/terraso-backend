# Copyright © 2026 Technology Matters
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

"""Regression tests for F1 (anonymous user enumeration) and F3 (anonymous
single-id IDOR via TerrasoRelayNode.get_node_from_global_id bypass)."""

import pytest
from graphene_django.utils.testing import graphql_query

pytestmark = pytest.mark.django_db


def _anon_query(query):
    """Run a GraphQL query without auth - the default Django test client
    sets no Authorization header and has no session."""
    return graphql_query(query, client=None)


# --- F1: anon must not enumerate users ---


def test_users_listing_returns_zero_to_anonymous(client_query_no_token, users):
    response = client_query_no_token("query { users { totalCount edges { node { email } } } }")
    body = response.json()
    assert body["data"]["users"]["totalCount"] == 0
    assert body["data"]["users"]["edges"] == []


def test_users_email_filter_returns_zero_to_anonymous(client_query_no_token, users):
    target_email = users[0].email
    response = client_query_no_token(
        'query { users(email_Iexact: "%s") { totalCount edges { node { email } } } }' % target_email
    )
    body = response.json()
    assert body["data"]["users"]["totalCount"] == 0


def test_user_by_id_returns_null_to_anonymous(client_query_no_token, users):
    response = client_query_no_token(
        'query { user(id: "%s") { email firstName lastName } }' % users[0].id
    )
    body = response.json()
    # Single-id User Field is non-nullable, so the response surfaces a schema
    # error rather than data.user=null. Either way, no user data leaks.
    assert "errors" in body or body["data"]["user"] is None


# --- F3: single-id queries must respect the Node's get_queryset ---


def test_anonymous_cannot_fetch_dataentry_by_id(client_query_no_token, group_data_entries):
    """DataEntryNode.get_queryset filters by membership.  Before the S2 fix,
    single-id query bypassed it and returned any data entry by UUID."""
    response = client_query_no_token(
        'query { dataEntry(id: "%s") { name url } }' % group_data_entries[0].id
    )
    body = response.json()
    assert "errors" in body or body["data"]["dataEntry"] is None


def test_anonymous_cannot_fetch_storymap_by_id(client_query_no_token, story_maps):
    """Unpublished story maps must not be readable by anonymous callers."""
    unpublished = next(s for s in story_maps if not s.is_published)
    response = client_query_no_token(
        'query { storyMap(id: "%s") { title isPublished } }' % unpublished.id
    )
    body = response.json()
    assert "errors" in body or body["data"]["storyMap"] is None


def test_anonymous_cannot_fetch_visualization_config_by_id(
    client_query_no_token, visualization_configs
):
    """VisualizationConfigNode previously skipped the membership filter for
    any field name other than 'visualizationConfigs', leaking single-id
    fetches.  Now top-level fetches apply the filter."""
    response = client_query_no_token(
        'query { visualizationConfig(id: "%s") { id title } }' % visualization_configs[0].id
    )
    body = response.json()
    assert "errors" in body or body["data"]["visualizationConfig"] is None


def test_anonymous_projects_listing_returns_zero(client_query_no_token):
    """F5: ProjectNode.get_queryset previously matched
    user_id IS NULL via LEFT OUTER JOIN, leaking projects with no
    memberships to anonymous callers."""
    from apps.project_management.models.projects import Project

    Project.objects.create(name="anon-bypass-probe")  # zero memberships
    response = client_query_no_token(
        "query { projects { totalCount edges { node { name } } } }"
    )
    body = response.json()
    assert body["data"]["projects"]["totalCount"] == 0
    assert body["data"]["projects"]["edges"] == []


def test_anonymous_cannot_fetch_project_by_id(client_query_no_token):
    """Projects with zero memberships were the exact data-shape that leaked
    via F5 — verify single-id fetch is also closed."""
    from apps.project_management.models.projects import Project

    p = Project.objects.create(name="anon-by-id-probe")
    response = client_query_no_token(
        'query { project(id: "%s") { name privacy } }' % p.id
    )
    body = response.json()
    assert "errors" in body or body["data"]["project"] is None
