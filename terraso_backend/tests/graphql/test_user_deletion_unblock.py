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

"""Schema-relaxation tests for the user-deletion unblock work
(security_audit_findings.md, side observation 1 under S5; plan doc
`account_deletion_author_snapshot_plan.md` v2).

`SiteNote.author` and `Site.owner` are now `null=True, SET_NULL`. This
file pins that the FKs accept null, that the cascade from a soft-deleted
User actually nulls them out, and that downstream code paths
(permission checks, site visibility, the is_author method, GraphQL
serialization) all keep working when the FK is null.

End-to-end UserDeleteMutation acceptance is a separate task — these
tests cover the schema/serialization side only.
"""

import pytest
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.core.models import User
from apps.project_management.models import Site
from apps.project_management.models.site_notes import SiteNote

pytestmark = pytest.mark.django_db


# --- Direct model behavior ---


def test_site_note_can_have_null_author():
    """Schema relaxation: SiteNote.author is now nullable."""
    site = mixer.blend(Site)
    note = SiteNote.objects.create(site=site, content="orphan note", author=None)
    assert note.author is None
    assert note.content == "orphan note"


def test_site_can_have_null_owner():
    """Schema relaxation: Site.owner was already null=True; just confirm
    it still accepts None after the on_delete change."""
    site = Site.objects.create(name="orphan-site", latitude=0, longitude=0, elevation=0, owner=None)
    assert site.owner is None


def test_user_soft_delete_nulls_authored_note(user):
    """Cascade behavior: deleting (soft-deleting) the author leaves the
    note in place with author=None. This is the whole point of the
    schema change — UserDeleteMutation no longer hits a RestrictedError."""
    site = mixer.blend(Site)
    note = SiteNote.objects.create(site=site, content="kept note", author=user)
    assert note.author_id == user.pk

    user.delete()  # safedelete soft-delete

    note.refresh_from_db()
    assert note.author is None
    assert note.content == "kept note"
    assert SiteNote.objects.filter(pk=note.pk).exists()


def test_user_soft_delete_cascades_to_owned_site(user):
    """Site.owner is CASCADE — a deleted user's unaffiliated owned sites
    die with them, including public ones."""
    site = Site.objects.create(name="kept-site", latitude=0, longitude=0, elevation=0, owner=user)
    assert site.owner_id == user.pk

    user.delete()  # safedelete soft-delete

    site.refresh_from_db()
    assert site.deleted_at is not None


# --- is_author and permission rules with null author/owner ---


def test_site_note_is_author_returns_false_for_null_author():
    """SiteNote.is_author(user) was already null-safe because `None == user`
    is False, but pin it explicitly — the equality protects against the
    deleted-author case."""
    site = mixer.blend(Site)
    note = SiteNote.objects.create(site=site, content="x", author=None)
    user = mixer.blend(User)
    assert note.is_author(user) is False


# Note: permission rules use bare `site.owner == user` equality, which is
# inherently null-safe (`None == user` → False).  Pre-implementation grep
# (security_audit_findings.md notes 2026-05-19) confirmed no deref of
# `.author` / `.owner` exists in any permission_rules file.  An explicit
# unit test would have to navigate the `require_unaffiliated_site` /
# `require_affiliated_site` precondition checks, which raise on orphan
# sites by design — those preconditions are enforced at the visibility
# layer (orphans are invisible to all callers except via the PUBLIC
# branch), so they never reach the permission-rule layer in practice.


# --- Site visibility with null owner (regression for filter_visible_sites) ---


def test_anon_still_sees_no_sites_when_owner_null(client_query_no_token):
    """Anonymous gets 0 sites — null owner doesn't accidentally relax this."""
    Site.objects.create(
        name="anon-orphan",
        latitude=0,
        longitude=0,
        elevation=0,
        owner=None,
        privacy=Site.PRIVATE,
    )
    response = client_query_no_token("{ sites { totalCount edges { node { id owner { id } } } } }")
    body = response.json()
    assert body["data"]["sites"]["totalCount"] == 0


def test_project_member_sees_orphan_project_site_with_stub_owner(client, project, project_user):
    """A site whose owner FK was nulled by the SET_NULL cascade can still
    be reached via its project. When project_user (a project member) views
    it, the owner field serializes as the deleted-user stub (id = nil
    UUID) rather than `null` — see deleted_user_stub_plan.md.

    (Visibility via the PUBLIC privacy branch is exercised separately in
    test_sites_public_visibility.py on the anonymous-access-scoping
    branch.)"""
    Site.objects.create(
        name="orphan-in-project",
        latitude=0,
        longitude=0,
        elevation=0,
        owner=None,
        project=project,
        privacy=Site.PRIVATE,
    )
    client.force_login(project_user)
    response = graphql_query(
        "{ sites { totalCount edges { node { name owner { id } privacy } } } }",
        client=client,
    )
    body = response.json()
    names = [edge["node"]["name"] for edge in body["data"]["sites"]["edges"]]
    assert "orphan-in-project" in names
    orphan_node = next(
        edge["node"]
        for edge in body["data"]["sites"]["edges"]
        if edge["node"]["name"] == "orphan-in-project"
    )
    assert orphan_node["owner"]["id"] == "00000000-0000-0000-0000-000000000000"


def test_stranger_cannot_see_private_orphan_site(client, user):
    """A site with owner=None and privacy=PRIVATE is visible to nobody —
    it doesn't match owner, membership, or public branches."""
    Site.objects.create(
        name="private-orphan",
        latitude=0,
        longitude=0,
        elevation=0,
        owner=None,
        privacy=Site.PRIVATE,
    )
    stranger = mixer.blend(User)
    client.force_login(stranger)
    response = graphql_query("{ sites { totalCount edges { node { name } } } }", client=client)
    body = response.json()
    names = [edge["node"]["name"] for edge in body["data"]["sites"]["edges"]]
    assert "private-orphan" not in names


# --- GraphQL serialization of null author/owner ---


def test_graphql_note_with_null_author_serializes_cleanly(client, user, project, project_user):
    """site.notes { author { id } } must serialize a null-author note
    cleanly. The resolver substitutes the deleted-user stub (id = nil
    UUID) instead of `null` — see deleted_user_stub_plan.md."""
    project_user_local = project_user  # already a project member
    site = Site.objects.create(
        name="serialize-test",
        latitude=0,
        longitude=0,
        elevation=0,
        project=project,
        privacy=Site.PRIVATE,
    )
    SiteNote.objects.create(site=site, content="with author", author=user)
    SiteNote.objects.create(site=site, content="without author", author=None)

    client.force_login(project_user_local)
    response = graphql_query(
        'query { site(id: "%s") { notes { edges { node { content author { id } } } } } }' % site.id,
        client=client,
    )
    body = response.json()
    assert "errors" not in body
    notes = body["data"]["site"]["notes"]["edges"]
    by_content = {edge["node"]["content"]: edge["node"] for edge in notes}
    assert by_content["with author"]["author"]["id"] == str(user.id)
    assert by_content["without author"]["author"]["id"] == "00000000-0000-0000-0000-000000000000"
