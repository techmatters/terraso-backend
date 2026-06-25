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

"""Public-site read visibility (product decision 2026-05-18, "loose"
interpretation): a Site flagged `privacy=PUBLIC` is readable by any
authenticated caller. Related data (notes, soil data) follows the same
visibility because those Nodes are only reachable via the Site
relation and have no get_queryset of their own.

Write access is unchanged — mutations still gate on ownership / project
membership regardless of the privacy flag.

Anonymous remains anon→0 sites (no change from F3); the future
data-portal feature is the entry point for anonymous public-site
discovery.
"""

import json

import pytest
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.core.models import User
from apps.project_management.models import Site
from apps.project_management.models.site_notes import SiteNote
from apps.soil_id.models.soil_data import SoilData

pytestmark = pytest.mark.django_db


@pytest.fixture
def stranger():
    """An authenticated user with no relationship to the site/project."""
    return mixer.blend(User)


def _force_login_as(client, user):
    client.force_login(user)


# --- Listing visibility ---


def test_public_site_listed_to_authenticated_stranger(client, stranger, user):
    """Site.privacy=PUBLIC must surface in `sites(...)` for an authenticated
    user who is neither owner nor project member."""
    public_site = Site.objects.create(
        name="public-site",
        latitude=0,
        longitude=0,
        elevation=0,
        privacy=Site.PUBLIC,
        owner=user,
    )

    _force_login_as(client, stranger)
    response = graphql_query(
        "{ sites { totalCount edges { node { id name privacy } } } }",
        client=client,
    )
    body = response.json()
    ids = [edge["node"]["id"] for edge in body["data"]["sites"]["edges"]]
    assert str(public_site.id) in ids


def test_private_site_not_listed_to_authenticated_stranger(client, stranger, user):
    """Site.privacy=PRIVATE must NOT surface to a stranger — the public
    branch is the only relaxation; private sites stay owner-or-member only."""
    private_site = Site.objects.create(
        name="private-site",
        latitude=0,
        longitude=0,
        elevation=0,
        privacy=Site.PRIVATE,
        owner=user,
    )

    _force_login_as(client, stranger)
    response = graphql_query(
        "{ sites { totalCount edges { node { id privacy } } } }",
        client=client,
    )
    body = response.json()
    ids = [edge["node"]["id"] for edge in body["data"]["sites"]["edges"]]
    assert str(private_site.id) not in ids


# --- Single-id fetch ---


def test_public_site_by_id_visible_to_authenticated_stranger(client, stranger, user):
    public_site = Site.objects.create(
        name="public-site",
        latitude=0,
        longitude=0,
        elevation=0,
        privacy=Site.PUBLIC,
        owner=user,
    )

    _force_login_as(client, stranger)
    response = graphql_query(
        'query { site(id: "%s") { id name privacy } }' % public_site.id, client=client
    )
    body = response.json()
    assert body["data"]["site"]["id"] == str(public_site.id)
    assert body["data"]["site"]["privacy"] == "PUBLIC"


def test_private_site_by_id_hidden_from_authenticated_stranger(client, stranger, user):
    private_site = Site.objects.create(
        name="private-site",
        latitude=0,
        longitude=0,
        elevation=0,
        privacy=Site.PRIVATE,
        owner=user,
    )

    _force_login_as(client, stranger)
    response = graphql_query('query { site(id: "%s") { id } }' % private_site.id, client=client)
    body = response.json()
    assert "errors" in body or body["data"]["site"] is None


# --- Anonymous coverage (regression: F3 still in force) ---


def test_anonymous_does_not_see_public_site_in_listing(client_query_no_token, user):
    Site.objects.create(
        name="public-anon-probe",
        latitude=0,
        longitude=0,
        elevation=0,
        privacy=Site.PUBLIC,
        owner=user,
    )
    response = client_query_no_token("{ sites { totalCount edges { node { id } } } }")
    body = response.json()
    assert body["data"]["sites"]["totalCount"] == 0
    assert body["data"]["sites"]["edges"] == []


def test_anonymous_does_not_see_public_site_by_id(client_query_no_token, user):
    public_site = Site.objects.create(
        name="public-anon-by-id",
        latitude=0,
        longitude=0,
        elevation=0,
        privacy=Site.PUBLIC,
        owner=user,
    )
    response = client_query_no_token('query { site(id: "%s") { id } }' % public_site.id)
    body = response.json()
    assert "errors" in body or body["data"]["site"] is None


# --- Owner / member visibility unchanged ---


def test_owner_sees_own_private_site(client, user):
    private_site = Site.objects.create(
        name="owner-private",
        latitude=0,
        longitude=0,
        elevation=0,
        privacy=Site.PRIVATE,
        owner=user,
    )
    _force_login_as(client, user)
    response = graphql_query(
        'query { site(id: "%s") { id privacy } }' % private_site.id, client=client
    )
    assert response.json()["data"]["site"]["id"] == str(private_site.id)


def test_owner_sees_own_public_site(client, user):
    public_site = Site.objects.create(
        name="owner-public",
        latitude=0,
        longitude=0,
        elevation=0,
        privacy=Site.PUBLIC,
        owner=user,
    )
    _force_login_as(client, user)
    response = graphql_query(
        'query { site(id: "%s") { id privacy } }' % public_site.id, client=client
    )
    assert response.json()["data"]["site"]["id"] == str(public_site.id)


def test_project_member_sees_private_project_site(client, project, project_user):
    private_site = Site.objects.create(
        name="project-private",
        latitude=0,
        longitude=0,
        elevation=0,
        privacy=Site.PRIVATE,
        project=project,
    )
    _force_login_as(client, project_user)
    response = graphql_query(
        'query { site(id: "%s") { id privacy } }' % private_site.id, client=client
    )
    assert response.json()["data"]["site"]["id"] == str(private_site.id)


# --- Loose semantics: related data on public sites visible to strangers ---


def test_public_site_notes_visible_to_authenticated_stranger(client, stranger, user):
    """Loose interpretation: if you can see a public site, you can see
    everything on it — notes, soil data, etc. The Note/SoilData Nodes
    don't have their own get_queryset, so they ride along on the Site's
    visibility decision."""
    public_site = Site.objects.create(
        name="public-with-notes",
        latitude=0,
        longitude=0,
        elevation=0,
        privacy=Site.PUBLIC,
        owner=user,
    )
    note = SiteNote.objects.create(site=public_site, content="public note", author=user)

    _force_login_as(client, stranger)
    response = graphql_query(
        'query { site(id: "%s") { notes { edges { node { id content } } } } }' % public_site.id,
        client=client,
    )
    body = response.json()
    note_ids = [edge["node"]["id"] for edge in body["data"]["site"]["notes"]["edges"]]
    assert str(note.id) in note_ids


def test_public_site_soil_data_visible_to_authenticated_stranger(client, stranger, user):
    public_site = Site.objects.create(
        name="public-with-soildata",
        latitude=0,
        longitude=0,
        elevation=0,
        privacy=Site.PUBLIC,
        owner=user,
    )
    SoilData.objects.create(site=public_site)

    _force_login_as(client, stranger)
    response = graphql_query(
        'query { site(id: "%s") { soilData { __typename } } }' % public_site.id,
        client=client,
    )
    body = response.json()
    assert body["data"]["site"]["soilData"] is not None
    assert body["data"]["site"]["soilData"]["__typename"] == "SoilDataNode"


# --- Write gating: publicness must not unlock mutations ---


def test_stranger_cannot_update_public_site(client, stranger, user):
    """Authentication + visibility is read-only. updateSite still requires
    ownership / project-management permission — the privacy flag does
    not relax write access."""
    public_site = Site.objects.create(
        name="public-write-probe",
        latitude=0,
        longitude=0,
        elevation=0,
        privacy=Site.PUBLIC,
        owner=user,
    )

    _force_login_as(client, stranger)
    mutation = """
        mutation updateSite($input: SiteUpdateMutationInput!) {
          updateSite(input: $input) { errors site { id name } }
        }
    """
    response = graphql_query(
        mutation,
        variables={"input": {"id": str(public_site.id), "name": "hijacked"}},
        client=client,
    )
    body = response.json()
    # Either a top-level error envelope or an errors payload on the mutation.
    failed = "errors" in body or (
        body.get("data", {}).get("updateSite", {}) is None
        or body["data"]["updateSite"].get("errors")
    )
    assert failed, f"expected stranger to be rejected; got {json.dumps(body)}"

    public_site.refresh_from_db()
    assert public_site.name == "public-write-probe"


def test_stranger_cannot_delete_public_site(client, stranger, user):
    public_site = Site.objects.create(
        name="public-delete-probe",
        latitude=0,
        longitude=0,
        elevation=0,
        privacy=Site.PUBLIC,
        owner=user,
    )

    _force_login_as(client, stranger)
    mutation = """
        mutation deleteSite($input: SiteDeleteMutationInput!) {
          deleteSite(input: $input) { errors site { id } }
        }
    """
    response = graphql_query(
        mutation,
        variables={"input": {"id": str(public_site.id)}},
        client=client,
    )
    body = response.json()
    failed = "errors" in body or (
        body.get("data", {}).get("deleteSite", {}) is None
        or body["data"]["deleteSite"].get("errors")
    )
    assert failed, f"expected stranger to be rejected; got {json.dumps(body)}"
    assert Site.objects.filter(id=public_site.id).exists()
