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

"""Null-handling tests for `SiteNote.author` and `Site.owner`.

Under the current user-deletion design (docs/user_soft_delete_plan.md):

- `SiteNote.author` is `null=True, SET_NULL` — notes on shared/project
  sites survive their author's deletion with `author=NULL`; the
  SiteNoteNode resolver substitutes `deleted_user_stub` so old clients
  don't crash dereferencing `author.id`.
- `Site.owner` is `null=True` but only for project-affiliated sites
  (per the `site_must_be_owned_once` XOR constraint). When an
  unaffiliated site's owner is soft-deleted, the site CASCADE-deletes
  rather than orphaning.

This file covers model behavior, permission-rule null-safety, and
GraphQL serialization of null `author`/`owner`. Related coverage lives
in `tests/core/models/test_user_deletion_gate.py` (gate + full cascade),
`tests/graphql/test_deleted_user_stub.py` (stub end-to-end), and
`tests/core/models/test_sitenote_author_restore.py` (undelete round-trip).
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
    site = mixer.blend(Site, owner=mixer.blend(User))
    note = SiteNote.objects.create(site=site, content="orphan note", author=None)
    assert note.author is None
    assert note.content == "orphan note"


def test_user_soft_delete_nulls_authored_note(user):
    """Cascade behavior: deleting the author leaves a note they wrote on
    someone else's site in place with author=None. Site is owned by a
    different user so `owner=CASCADE` doesn't take the whole site down."""
    other = mixer.blend(User)
    site = mixer.blend(Site, owner=other)
    note = SiteNote.objects.create(site=site, content="kept note", author=user)
    assert note.author_id == user.pk

    user.delete()  # safedelete soft-delete

    note.refresh_from_db()
    assert note.author is None
    assert note.content == "kept note"
    assert SiteNote.objects.filter(pk=note.pk).exists()


def test_user_soft_delete_cascades_to_owned_site(user):
    """Soft-deleting the user soft-deletes their unaffiliated owned sites
    along with them."""
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
    site = mixer.blend(Site, owner=mixer.blend(User))
    note = SiteNote.objects.create(site=site, content="x", author=None)
    user = mixer.blend(User)
    assert note.is_author(user) is False


# Note: permission rules use bare `site.owner == user` equality, which is
# inherently null-safe (`None == user` → False). Pre-implementation grep
# (security_audit_findings.md notes 2026-05-19) confirmed no deref of
# `.author` / `.owner` exists in any permission_rules file. Site.owner
# can only be null on project-affiliated sites (site_must_be_owned_once
# constraint), so the null-owner permission path is exercised by
# test_project_member_sees_project_site_with_null_owner below.


# --- Site visibility with null owner on project-affiliated sites ---


def test_project_member_sees_project_site_with_null_owner(client, project, project_user):
    """A project-affiliated site has owner=None by design (the check
    constraint forbids both owner and project being set). When a project
    member views it, the owner field serializes as `null`."""
    Site.objects.create(
        name="project-site",
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
    assert "project-site" in names
    project_site_node = next(
        edge["node"]
        for edge in body["data"]["sites"]["edges"]
        if edge["node"]["name"] == "project-site"
    )
    assert project_site_node["owner"] is None


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
