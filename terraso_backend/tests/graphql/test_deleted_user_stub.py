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

"""Server-side deleted-user stub: when SiteNote.author is null (the
SET_NULL cascade from UserDeleteMutation nulls it on shared-project
notes that must survive their author's deletion), the SiteNoteNode
resolver returns an unsaved User instance with id=DELETED_USER_ID and
English "Deleted User" name. Old clients that dereference author.id
don't crash; new clients detect DELETED_USER_ID and substitute a
localized label.

Plan: terraso-backend-research/deleted_user_stub_plan.md (2026-05-19).
"""

import pytest
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.core.models import User
from apps.core.models.users import (
    DELETED_USER_FIRST_NAME,
    DELETED_USER_ID,
    DELETED_USER_LAST_NAME,
    deleted_user_stub,
)
from apps.project_management.models import Site
from apps.project_management.models.site_notes import SiteNote

pytestmark = pytest.mark.django_db


# --- Factory ---


def test_deleted_user_stub_has_sentinel_id_and_label():
    stub = deleted_user_stub()
    assert str(stub.id) == DELETED_USER_ID
    assert stub.first_name == DELETED_USER_FIRST_NAME
    assert stub.last_name == DELETED_USER_LAST_NAME
    assert stub.email == ""
    assert stub.profile_image == ""
    assert stub.is_active is False


def test_deleted_user_stub_is_not_persisted():
    """The stub is an in-memory instance — calling it must not insert
    rows or otherwise touch the DB."""
    before = User.objects.count()
    deleted_user_stub()
    deleted_user_stub()
    deleted_user_stub()
    assert User.objects.count() == before


def test_no_real_user_can_collide_with_sentinel_id():
    """Defense-in-depth: even if someone manually creates a user with
    the sentinel id, the GraphQL `user(id: DELETED_USER_ID)` lookup
    returns null because Django's default uuid.uuid4 generation never
    produces the nil UUID. Test the contract that no row currently
    holds this id (a regression check rather than a true invariant)."""
    assert not User.objects.filter(id=DELETED_USER_ID).exists()


# --- SiteNoteNode.author resolver ---


def test_site_note_with_null_author_returns_stub(client, user, project, project_user):
    """A note whose author was deleted (SET_NULL) is returned with a
    stub author payload so old clients can render it."""
    site = Site.objects.create(
        name="stub-note-site",
        latitude=0,
        longitude=0,
        elevation=0,
        project=project,
        privacy=Site.PRIVATE,
    )
    note = SiteNote.objects.create(site=site, content="orphaned", author=None)

    client.force_login(project_user)
    response = graphql_query(
        'query { site(id: "%s") { notes { edges { node { id author { id firstName lastName email } } } } } }'
        % site.id,
        client=client,
    )
    body = response.json()
    assert "errors" not in body
    edges = body["data"]["site"]["notes"]["edges"]
    found = next(e for e in edges if e["node"]["id"] == str(note.id))
    author = found["node"]["author"]
    assert author is not None
    assert author["id"] == DELETED_USER_ID
    assert author["firstName"] == DELETED_USER_FIRST_NAME
    assert author["lastName"] == DELETED_USER_LAST_NAME
    assert author["email"] == ""


def test_site_note_with_real_author_returns_real_user(client, user, project, project_user):
    """Sanity: a note whose author is a real user must serialize the
    real user, not the stub."""
    site = Site.objects.create(
        name="real-author-site",
        latitude=0,
        longitude=0,
        elevation=0,
        project=project,
        privacy=Site.PRIVATE,
    )
    note = SiteNote.objects.create(site=site, content="real note", author=user)

    client.force_login(project_user)
    response = graphql_query(
        'query { site(id: "%s") { notes { edges { node { id author { id email } } } } } }'
        % site.id,
        client=client,
    )
    body = response.json()
    edges = body["data"]["site"]["notes"]["edges"]
    found = next(e for e in edges if e["node"]["id"] == str(note.id))
    assert found["node"]["author"]["id"] == str(user.id)
    assert found["node"]["author"]["email"] == user.email


# --- Soft-delete end-to-end ---


def test_soft_deleting_user_makes_their_notes_serialize_with_stub(client, project, project_user):
    """Drive the full cascade: a user authors a note; the user soft-deletes;
    the note now serializes with the stub author. This is the scenario
    that prompted the plan — the symptom the stub prevents on old clients."""
    deleted_author = mixer.blend(User, email="deleted-author@example.test")
    site = Site.objects.create(
        name="cascade-site",
        latitude=0,
        longitude=0,
        elevation=0,
        project=project,
        privacy=Site.PRIVATE,
    )
    note = SiteNote.objects.create(site=site, content="surviving note", author=deleted_author)

    # Soft-delete the author. SiteNote.author is SET_NULL → note.author
    # becomes None; the resolver substitutes the stub.
    deleted_author.delete()
    note.refresh_from_db()
    assert note.author is None

    client.force_login(project_user)
    response = graphql_query(
        'query { site(id: "%s") { notes { edges { node { id author { id firstName } } } } } }'
        % site.id,
        client=client,
    )
    body = response.json()
    edges = body["data"]["site"]["notes"]["edges"]
    found = next(e for e in edges if e["node"]["id"] == str(note.id))
    assert found["node"]["author"]["id"] == DELETED_USER_ID
    assert found["node"]["author"]["firstName"] == DELETED_USER_FIRST_NAME


# --- Stub traversal safety ---


def test_stub_user_preferences_traversal_returns_empty(client, user, project, project_user):
    """Old clients may select related fields on author (e.g., preferences).
    The stub's id is the nil UUID; no UserPreference row has user_id=NIL_UUID,
    so the connection renders as an empty array rather than crashing the
    resolver. (UserNode also has a `memberships` reverse relation in the
    model, but it is not exposed in the GraphQL schema — see UserNode.Meta
    in apps/graphql/schema/users.py — so we don't test it here.)"""
    site = Site.objects.create(
        name="traversal-site",
        latitude=0,
        longitude=0,
        elevation=0,
        project=project,
        privacy=Site.PRIVATE,
    )
    SiteNote.objects.create(site=site, content="x", author=None)

    client.force_login(project_user)
    response = graphql_query(
        'query { site(id: "%s") { notes { edges { node { author { id preferences { edges { node { id } } } } } } } } }'
        % site.id,
        client=client,
    )
    body = response.json()
    assert "errors" not in body
    author = body["data"]["site"]["notes"]["edges"][0]["node"]["author"]
    assert author["preferences"]["edges"] == []
