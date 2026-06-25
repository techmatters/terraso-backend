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

from apps.core.models import UserPreference

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


def test_email_iexact_works_for_regular_user(client_query, user, users):
    """Authenticated callers can still do exact-email lookups (the legitimate
    add-team-member flow uses email_Iexact)."""
    target = users[1]
    response = client_query(
        'query { users(email_Iexact: "%s") { totalCount edges { node { email } } } }' % target.email
    )
    body = response.json()
    assert body["data"]["users"]["totalCount"] == 1
    assert body["data"]["users"]["edges"][0]["node"]["email"] == target.email


def test_email_icontains_returns_zero_for_regular_user(client_query, user, users):
    """Substring filters are gated to superusers; a regular authenticated
    caller using email_Icontains gets an empty result rather than the
    user table."""
    domain = "@" + users[1].email.split("@")[1]
    response = client_query('query { users(email_Icontains: "%s") { totalCount } }' % domain)
    assert response.json()["data"]["users"]["totalCount"] == 0


def test_email_icontains_works_for_superuser(client_query, user, users):
    """Superuser can still use the substring filter (kept in schema for
    potential admin/support workflows)."""
    user.is_superuser = True
    user.save()
    domain = "@" + users[1].email.split("@")[1]
    response = client_query('query { users(email_Icontains: "%s") { totalCount } }' % domain)
    assert response.json()["data"]["users"]["totalCount"] >= 1


def test_first_name_icontains_returns_zero_for_regular_user(client_query, user, users):
    users[1].first_name = "UniqueFirstName"
    users[1].save()
    response = client_query('query { users(firstName_Icontains: "Unique") { totalCount } }')
    assert response.json()["data"]["users"]["totalCount"] == 0


def test_authenticated_user_cannot_enumerate_all_users(client_query, user, users):
    """Open OAuth signup makes "authenticated" a near-public bar, so the
    unfiltered users connection must not hand a regular caller the whole
    directory — only exact-email lookups are allowed (see UserFilter.qs)."""
    response = client_query("query { users { totalCount edges { node { email } } } }")
    body = response.json()
    assert body["data"]["users"]["totalCount"] == 0
    assert body["data"]["users"]["edges"] == []


def test_project_filter_without_exact_email_returns_zero_for_regular_user(
    client_query, user, users
):
    """`users(project: ...)` without an exact email is a list/enumeration
    request (and never checked caller membership), so it is denied for
    non-superusers regardless of whether the project exists."""
    response = client_query(
        'query { users(project: "00000000-0000-0000-0000-000000000000") { totalCount } }'
    )
    assert response.json()["data"]["users"]["totalCount"] == 0


def test_superuser_can_list_all_users(client_query, user, users):
    """Superusers retain full enumeration (kept for admin/support workflows)."""
    user.is_superuser = True
    user.save()
    response = client_query("query { users { totalCount } }")
    assert response.json()["data"]["users"]["totalCount"] == len(users)


def test_email_probe_hides_other_users_preferences(client_query, user, users):
    """The exact-email lookup must not disclose another user's preferences
    (language, notification opt-ins, account-deletion-request); identity
    fields still resolve, but the preferences connection is owner-scoped."""
    target = users[1]
    UserPreference.objects.create(user=target, key="language", value="es-EC")
    response = client_query(
        'query { users(email_Iexact: "%s") { edges { node { email '
        "preferences { edges { node { key value } } } } } } }" % target.email
    )
    node = response.json()["data"]["users"]["edges"][0]["node"]
    assert node["email"] == target.email
    assert node["preferences"]["edges"] == []


def test_user_can_read_own_preferences(client_query, user, users):
    """A caller's own preferences stay readable — the userProfile flow loads
    the logged-in user's language/notification settings this way."""
    UserPreference.objects.create(user=user, key="language", value="en-US")
    response = client_query(
        'query { users(email_Iexact: "%s") { edges { node { '
        "preferences { edges { node { key value } } } } } } }" % user.email
    )
    prefs = response.json()["data"]["users"]["edges"][0]["node"]["preferences"]["edges"]
    assert any(e["node"]["key"] == "language" and e["node"]["value"] == "en-US" for e in prefs)


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
    response = client_query_no_token("query { projects { totalCount edges { node { name } } } }")
    body = response.json()
    assert body["data"]["projects"]["totalCount"] == 0
    assert body["data"]["projects"]["edges"] == []


def test_anonymous_cannot_fetch_project_by_id(client_query_no_token):
    """Projects with zero memberships were the exact data-shape that leaked
    via F5 — verify single-id fetch is also closed."""
    from apps.project_management.models.projects import Project

    p = Project.objects.create(name="anon-by-id-probe")
    response = client_query_no_token('query { project(id: "%s") { name privacy } }' % p.id)
    body = response.json()
    assert "errors" in body or body["data"]["project"] is None


# --- Q7 / Q12: GroupAssociation scoping for anonymous callers ---
#
# Q7 (`groupAssociation(id)`) and Q12 (`groupAssociations(...)`) were
# inconclusive in Phase 2 because the local DB had no GroupAssociation
# rows.  These tests build the previously-missing fixture data and
# pin the **intended public behavior** (product decision 2026-05-17,
# "Position A"): the parent→child relationship between two Groups is
# public information, consistent with Q3 (single Group) and Q8 (Groups
# listing) being public-by-design.
#
# What the tests pin:
#   - Anonymous CAN list non-default-group associations.
#   - Anonymous CAN fetch a non-default-group association by id.
#   - The existing default-landscape-group filter in
#     GroupAssociationNode.get_queryset still excludes associations
#     where either side is a default-landscape group (those are
#     system-generated plumbing, not user-meaningful relationships).
#
# If product reverses on this — e.g., relationship metadata between
# Groups turns out to be politically sensitive — these tests should
# flip to assert anon→none, and GroupAssociationNode.get_queryset
# gains an `is_anonymous → .none()` short-circuit matching F1/F5.


@pytest.fixture
def group_association_fixture():
    """Two associations:
    - assoc_regular: regular_a → regular_b (NOT excluded by the default-group guard)
    - assoc_default: regular_a → group_in_default_landscape_group (excluded by guard)
    """
    from mixer.backend.django import mixer

    from apps.core.models import Group, GroupAssociation, Landscape
    from apps.core.models.landscapes import LandscapeGroup

    regular_a = mixer.blend(Group, name="anon-probe-regular-a")
    regular_b = mixer.blend(Group, name="anon-probe-regular-b")
    in_default = mixer.blend(Group, name="anon-probe-in-default")

    landscape = mixer.blend(Landscape, name="anon-probe-landscape")
    LandscapeGroup.objects.create(
        landscape=landscape, group=in_default, is_default_landscape_group=True
    )

    assoc_regular = GroupAssociation.objects.create(parent_group=regular_a, child_group=regular_b)
    assoc_default = GroupAssociation.objects.create(parent_group=regular_a, child_group=in_default)
    return {
        "assoc_regular": assoc_regular,
        "assoc_default": assoc_default,
        "regular_a": regular_a,
        "regular_b": regular_b,
        "in_default": in_default,
    }


def test_anonymous_group_associations_listing_returns_non_default_only(
    client_query_no_token, group_association_fixture
):
    """Q12 (Position A — intentionally public):
    Anonymous can list GroupAssociations between non-default-landscape
    groups. The default-landscape-group filter still removes plumbing
    associations from the listing."""
    response = client_query_no_token(
        "query { groupAssociations { totalCount edges { node { id } } } }"
    )
    body = response.json()
    expected_id = str(group_association_fixture["assoc_regular"].id)
    excluded_id = str(group_association_fixture["assoc_default"].id)
    ids = [edge["node"]["id"] for edge in body["data"]["groupAssociations"]["edges"]]
    assert expected_id in ids
    assert excluded_id not in ids


def test_anonymous_can_fetch_non_default_group_association_by_id(
    client_query_no_token, group_association_fixture
):
    """Q7 (Position A — intentionally public):
    Anonymous can fetch a single GroupAssociation between non-default
    groups. Q3 (single Group) and Q8 (Groups listing) are already
    public-by-design; the relationship between two public Groups is
    public information too."""
    assoc = group_association_fixture["assoc_regular"]
    response = client_query_no_token(
        'query { groupAssociation(id: "%s") { id parentGroup { slug } } }' % assoc.id
    )
    body = response.json()
    assert body["data"]["groupAssociation"]["id"] == str(assoc.id)
    assert (
        body["data"]["groupAssociation"]["parentGroup"]["slug"]
        == group_association_fixture["regular_a"].slug
    )


def test_anonymous_cannot_fetch_default_group_association_by_id(
    client_query_no_token, group_association_fixture
):
    """The default-landscape-group filter excludes plumbing associations
    from every caller, anonymous or not. This is the same behavior an
    authenticated caller would observe; it's a content filter, not an
    auth filter."""
    assoc = group_association_fixture["assoc_default"]
    response = client_query_no_token(
        'query { groupAssociation(id: "%s") { id parentGroup { slug } } }' % assoc.id
    )
    body = response.json()
    assert "errors" in body or body["data"]["groupAssociation"] is None
