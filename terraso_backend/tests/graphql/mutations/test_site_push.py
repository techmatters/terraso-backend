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

import json
import uuid
from unittest.mock import patch

import pytest
from mixer.backend.django import mixer

from apps.project_management.models import Project, Site, SiteNote, SitePushHistory
from apps.soil_id.models import SoilData, SoilMetadata

pytestmark = pytest.mark.django_db

# ---------------------------------------------------------------------------
# GraphQL query string
# ---------------------------------------------------------------------------

PUSH_USER_DATA_QUERY = """
mutation pushUserData($input: UserDataPushInput!) {
  pushUserData(input: $input) {
    siteResults {
      siteId
      result {
        __typename
        ... on SitePushEntrySuccess {
          site {
            id
            name
            latitude
            longitude
            elevation
            privacy
            notes {
              edges {
                node {
                  id
                  content
                }
              }
            }
          }
        }
        ... on SitePushEntryFailure {
          reason
        }
      }
    }
  }
}
"""


def do_push(client_query, site_entries):
    """Helper: execute pushUserData with only siteEntries."""
    return client_query(
        PUSH_USER_DATA_QUERY,
        variables={"input": {"siteEntries": site_entries}},
    )


def get_site_results(response):
    content = json.loads(response.content)
    assert "errors" not in content, content.get("errors")
    return content["data"]["pushUserData"]["siteResults"]


def new_site_entry(site_id=None, **kwargs):
    """Minimal valid entry for a new site."""
    return {
        "siteId": site_id or str(uuid.uuid4()),
        "isNew": True,
        "name": kwargs.get("name", "Test Site"),
        "latitude": kwargs.get("latitude", 1.0),
        "longitude": kwargs.get("longitude", 2.0),
        "elevation": kwargs.get("elevation", None),
        "privacy": kwargs.get("privacy", "PRIVATE"),
        "projectId": kwargs.get("projectId", None),
        "newNotes": kwargs.get("newNotes", []),
        "updatedNotes": [],
        "deletedNoteIds": [],
    }


def update_site_entry(site_id, **kwargs):
    """Entry for updating an existing site."""
    return {
        "siteId": str(site_id),
        "isNew": False,
        "name": kwargs.get("name", None),
        "latitude": kwargs.get("latitude", None),
        "longitude": kwargs.get("longitude", None),
        "elevation": kwargs.get("elevation", None),
        "privacy": kwargs.get("privacy", None),
        "projectId": kwargs.get("projectId", None),
        "newNotes": kwargs.get("newNotes", []),
        "updatedNotes": kwargs.get("updatedNotes", []),
        "deletedNoteIds": kwargs.get("deletedNoteIds", []),
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def owned_site(user):
    return Site.objects.create(
        name="Owner Site", latitude=1.0, longitude=2.0, owner=user, privacy="PRIVATE"
    )


@pytest.fixture
def site_note(user, owned_site):
    return SiteNote.objects.create(site=owned_site, content="Original content", author=user)


# ---------------------------------------------------------------------------
# New site — success cases
# ---------------------------------------------------------------------------


def test_add_new_site_success(client_query, user):
    site_id = str(uuid.uuid4())
    entry = new_site_entry(site_id=site_id, name="My Site", latitude=10.0, longitude=20.0)

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert len(results) == 1
    result = results[0]
    assert result["siteId"] == site_id
    assert result["result"]["__typename"] == "SitePushEntrySuccess"
    assert result["result"]["site"]["name"] == "My Site"
    assert result["result"]["site"]["id"] == site_id

    # Site and associated soil records created in DB
    site = Site.objects.get(id=site_id)
    assert site.owner == user
    assert SoilData.objects.filter(site=site).exists()
    assert SoilMetadata.objects.filter(site=site).exists()


def test_add_new_site_history_logged(client_query, user):
    site_id = str(uuid.uuid4())
    do_push(client_query, [new_site_entry(site_id=site_id)])

    history = SitePushHistory.objects.filter(changed_by=user)
    assert history.count() == 1
    assert history.first().update_succeeded is True
    assert history.first().update_failure_reason is None


def test_add_new_site_idempotent(client_query, user):
    """Pushing the same UUID twice returns the existing site without error."""
    site_id = str(uuid.uuid4())
    entry = new_site_entry(site_id=site_id, name="Original")

    do_push(client_query, [entry])
    response2 = do_push(client_query, [entry])
    results = get_site_results(response2)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"
    assert Site.objects.filter(id=site_id).count() == 1


def test_add_new_site_with_notes(client_query, user):
    site_id = str(uuid.uuid4())
    note_id = str(uuid.uuid4())
    entry = new_site_entry(
        site_id=site_id,
        newNotes=[{"id": note_id, "content": "Hello world"}],
    )

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"
    note = SiteNote.objects.get(id=note_id)
    assert note.content == "Hello world"
    assert note.author == user
    assert str(note.site_id) == site_id


def test_add_new_site_note_idempotent(client_query, user):
    """Pushing the same note UUID twice doesn't create a duplicate."""
    site_id = str(uuid.uuid4())
    note_id = str(uuid.uuid4())
    entry = new_site_entry(
        site_id=site_id,
        newNotes=[{"id": note_id, "content": "Hello"}],
    )
    do_push(client_query, [entry])
    response2 = do_push(client_query, [entry])
    results = get_site_results(response2)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"
    assert SiteNote.objects.filter(id=note_id).count() == 1


def test_add_new_site_with_project(client_query, user):
    project = mixer.blend(Project)
    project.add_manager(user)
    site_id = str(uuid.uuid4())
    entry = new_site_entry(site_id=site_id, projectId=str(project.id))

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"
    site = Site.objects.get(id=site_id)
    assert site.project == project
    assert site.owner is None


def test_add_new_site_project_not_found_creates_without_affiliation(client_query, user):
    """When the project doesn't exist, site is created as owner-only (silent drop)."""
    site_id = str(uuid.uuid4())
    entry = new_site_entry(site_id=site_id, projectId=str(uuid.uuid4()))

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"
    site = Site.objects.get(id=site_id)
    assert site.owner == user
    assert site.project is None


def test_add_new_site_no_project_permission_creates_without_affiliation(client_query, user):
    """When the user lacks permission to add to a project, site is created as owner-only (silent drop)."""
    project = mixer.blend(Project)
    # user is not a member of the project at all
    site_id = str(uuid.uuid4())
    entry = new_site_entry(site_id=site_id, projectId=str(project.id))

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"
    site = Site.objects.get(id=site_id)
    assert site.owner == user
    assert site.project is None


# ---------------------------------------------------------------------------
# Existing site — update cases
# ---------------------------------------------------------------------------


def test_update_site_success(client_query, user, owned_site):
    entry = update_site_entry(owned_site.id, name="Renamed Site")

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"
    owned_site.refresh_from_db()
    assert owned_site.name == "Renamed Site"


def test_update_site_history_logged(client_query, user, owned_site):
    do_push(client_query, [update_site_entry(owned_site.id, name="New")])

    history = SitePushHistory.objects.filter(changed_by=user)
    assert history.count() == 1
    assert history.first().update_succeeded is True


def test_update_site_does_not_exist(client_query, user):
    entry = update_site_entry(uuid.uuid4(), name="Ghost")

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntryFailure"
    assert results[0]["result"]["reason"] == "SITE_DOES_NOT_EXIST"


def test_update_site_not_allowed(client_query, user):
    """User without UPDATE_SETTINGS permission on a project site gets NOT_ALLOWED."""
    other_site = mixer.blend(Site, project=mixer.blend(Project))
    entry = update_site_entry(other_site.id, name="Stolen")

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntryFailure"
    assert results[0]["result"]["reason"] == "NOT_ALLOWED"


def test_update_site_history_logged_on_failure(client_query, user):
    entry = update_site_entry(uuid.uuid4())  # non-existent site

    do_push(client_query, [entry])

    history = SitePushHistory.objects.filter(changed_by=user)
    assert history.count() == 1
    assert history.first().update_succeeded is False
    assert history.first().update_failure_reason == "SITE_DOES_NOT_EXIST"


# ---------------------------------------------------------------------------
# Note operations on existing site
# ---------------------------------------------------------------------------


def test_update_note_success(client_query, user, owned_site, site_note):
    entry = update_site_entry(
        owned_site.id,
        updatedNotes=[{"id": str(site_note.id), "content": "Updated content"}],
    )

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"
    site_note.refresh_from_db()
    assert site_note.content == "Updated content"


def test_update_note_does_not_exist_is_skipped(client_query, user, owned_site):
    """Updating a note that doesn't exist is silently skipped (idempotent)."""
    entry = update_site_entry(
        owned_site.id,
        updatedNotes=[{"id": str(uuid.uuid4()), "content": "Phantom edit"}],
    )

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"


def test_update_note_not_allowed_is_skipped(client_query, user):
    """Editing a note you didn't author on a project site is silently skipped
    (best-effort: the entry succeeds, but the note content is unchanged)."""
    project = mixer.blend(Project)
    project.add_manager(user)
    project_site = Site.objects.create(
        name="Project Site", latitude=1.0, longitude=2.0, project=project, privacy="private"
    )
    other_user = mixer.blend("core.User")
    note = SiteNote.objects.create(site=project_site, content="Other's note", author=other_user)
    entry = update_site_entry(
        project_site.id,
        updatedNotes=[{"id": str(note.id), "content": "Overwrite"}],
    )

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"
    note.refresh_from_db()
    assert note.content == "Other's note"  # unchanged — edit was skipped


def test_delete_note_success(client_query, user, owned_site, site_note):
    entry = update_site_entry(owned_site.id, deletedNoteIds=[str(site_note.id)])

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"
    assert not SiteNote.objects.filter(id=site_note.id).exists()


def test_delete_note_already_deleted_is_success(client_query, user, owned_site):
    """Deleting a note that doesn't exist is treated as success (idempotent)."""
    entry = update_site_entry(owned_site.id, deletedNoteIds=[str(uuid.uuid4())])

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"


def test_delete_note_not_allowed(client_query, user):
    """A non-manager user cannot make changes (including note deletion) on a project site."""
    project = mixer.blend(Project)
    # user is NOT added as a manager — no UPDATE_SETTINGS permission on affiliated site
    project_site = Site.objects.create(
        name="Project Site", latitude=1.0, longitude=2.0, project=project, privacy="private"
    )
    other_user = mixer.blend("core.User")
    note = SiteNote.objects.create(site=project_site, content="Other's note", author=other_user)
    entry = update_site_entry(project_site.id, deletedNoteIds=[str(note.id)])

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntryFailure"
    assert results[0]["result"]["reason"] == "NOT_ALLOWED"
    assert SiteNote.objects.filter(id=note.id).exists()


# ---------------------------------------------------------------------------
# Per-site atomicity
# ---------------------------------------------------------------------------


def test_missing_note_update_does_not_roll_back_site_field_update(client_query, user, owned_site):
    """
    Updating a note that doesn't exist is silently skipped, so other changes
    in the same entry (like site field updates) still succeed.
    """
    entry = update_site_entry(
        owned_site.id,
        name="Should Succeed",
        updatedNotes=[{"id": str(uuid.uuid4()), "content": "Phantom"}],
    )

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"

    owned_site.refresh_from_db()
    assert owned_site.name == "Should Succeed"


def test_new_site_with_unauthorized_note_edit_still_creates_site(client_query, user):
    """
    Note operations are best-effort: if editing a note fails permission, the
    edit is skipped but the rest of the entry (including site creation) succeeds.
    """
    # Create an existing note owned by another user so EDIT_NOTE will fail
    other_user = mixer.blend("core.User")
    other_site = mixer.blend(Site, owner=other_user)
    existing_note = SiteNote.objects.create(site=other_site, content="Existing", author=other_user)

    site_id = str(uuid.uuid4())
    entry = new_site_entry(
        site_id=site_id,
        newNotes=[],
    )
    # Force a note permission failure by trying to update a note the user doesn't own
    entry["updatedNotes"] = [{"id": str(existing_note.id), "content": "Stolen"}]

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"
    # Site was still created despite the skipped note edit
    assert Site.objects.filter(id=site_id).exists()
    # The other user's note was not modified
    existing_note.refresh_from_db()
    assert existing_note.content == "Existing"


# ---------------------------------------------------------------------------
# Contributor best-effort permissions
# ---------------------------------------------------------------------------


def test_contributor_can_push_notes_on_project_site(client_query, user):
    """A project contributor can create notes on an affiliated site even though
    they don't have UPDATE_SETTINGS permission (which is manager-only)."""
    project = mixer.blend(Project)
    project.add_contributor(user)
    project_site = Site.objects.create(
        name="Project Site", latitude=1.0, longitude=2.0, project=project, privacy="private"
    )
    note_id = str(uuid.uuid4())
    entry = update_site_entry(
        project_site.id,
        newNotes=[{"id": note_id, "content": "Contributor note"}],
    )

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"
    note = SiteNote.objects.get(id=note_id)
    assert note.content == "Contributor note"
    assert note.author == user


def test_contributor_field_updates_skipped_on_project_site(client_query, user):
    """A contributor's field updates (name, lat, etc.) are silently skipped on
    an affiliated site — the entry succeeds but the fields are unchanged."""
    project = mixer.blend(Project)
    project.add_contributor(user)
    project_site = Site.objects.create(
        name="Original Name", latitude=1.0, longitude=2.0, project=project, privacy="private"
    )
    entry = update_site_entry(project_site.id, name="Contributor Rename")

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"
    project_site.refresh_from_db()
    assert project_site.name == "Original Name"  # unchanged — field update skipped


def test_contributor_mixed_entry_notes_applied_fields_skipped(client_query, user):
    """When a contributor sends both field updates and notes in one entry, the
    field updates are skipped (no permission) but the notes are applied."""
    project = mixer.blend(Project)
    project.add_contributor(user)
    project_site = Site.objects.create(
        name="Original", latitude=1.0, longitude=2.0, project=project, privacy="private"
    )
    note_id = str(uuid.uuid4())
    entry = update_site_entry(
        project_site.id,
        name="Should Not Change",
        newNotes=[{"id": note_id, "content": "Should be created"}],
    )

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"
    project_site.refresh_from_db()
    assert project_site.name == "Original"  # field update skipped
    assert SiteNote.objects.filter(id=note_id).exists()  # note created


def test_contributor_can_set_null_elevation(client_query, user):
    """A contributor can set elevation on a site where it's currently null —
    this is initial data entry, not a settings change."""
    project = mixer.blend(Project)
    project.add_contributor(user)
    project_site = Site.objects.create(
        name="No Elevation",
        latitude=1.0,
        longitude=2.0,
        project=project,
        privacy="private",
        elevation=None,
    )
    entry = update_site_entry(project_site.id, elevation=100.5)

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"
    project_site.refresh_from_db()
    assert project_site.elevation == 100.5


def test_contributor_cannot_overwrite_existing_elevation(client_query, user):
    """A contributor cannot change elevation from one value to another —
    that's a settings change requiring UPDATE_SETTINGS (manager-only)."""
    project = mixer.blend(Project)
    project.add_contributor(user)
    project_site = Site.objects.create(
        name="Has Elevation",
        latitude=1.0,
        longitude=2.0,
        project=project,
        privacy="private",
        elevation=50.0,
    )
    entry = update_site_entry(project_site.id, elevation=100.5)

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"
    project_site.refresh_from_db()
    assert project_site.elevation == 50.0  # unchanged


def test_contributor_edit_own_note_skips_others_note(client_query, user):
    """A contributor can edit their own note but editing another user's note
    is silently skipped — both operations in the same entry."""
    project = mixer.blend(Project)
    project.add_contributor(user)
    project_site = Site.objects.create(
        name="Project Site", latitude=1.0, longitude=2.0, project=project, privacy="private"
    )
    own_note = SiteNote.objects.create(site=project_site, content="My note", author=user)
    other_user = mixer.blend("core.User")
    others_note = SiteNote.objects.create(
        site=project_site, content="Their note", author=other_user
    )
    entry = update_site_entry(
        project_site.id,
        updatedNotes=[
            {"id": str(own_note.id), "content": "My updated note"},
            {"id": str(others_note.id), "content": "Stolen content"},
        ],
    )

    response = do_push(client_query, [entry])
    results = get_site_results(response)

    assert results[0]["result"]["__typename"] == "SitePushEntrySuccess"
    own_note.refresh_from_db()
    assert own_note.content == "My updated note"  # own note updated
    others_note.refresh_from_db()
    assert others_note.content == "Their note"  # other's note unchanged


# ---------------------------------------------------------------------------
# Partial success across multiple sites
# ---------------------------------------------------------------------------


def test_partial_success_one_site_fails_other_succeeds(client_query, user):
    good_site_id = str(uuid.uuid4())
    bad_site_id = str(uuid.uuid4())  # will try to update non-existent site

    entries = [
        new_site_entry(site_id=good_site_id, name="Good"),
        update_site_entry(bad_site_id, name="Bad"),  # SITE_DOES_NOT_EXIST
    ]

    response = do_push(client_query, entries)
    results = get_site_results(response)

    assert len(results) == 2
    by_id = {r["siteId"]: r for r in results}

    assert by_id[good_site_id]["result"]["__typename"] == "SitePushEntrySuccess"
    assert by_id[bad_site_id]["result"]["__typename"] == "SitePushEntryFailure"
    assert by_id[bad_site_id]["result"]["reason"] == "SITE_DOES_NOT_EXIST"

    # Good site was created despite the other failing
    assert Site.objects.filter(id=good_site_id).exists()


# ---------------------------------------------------------------------------
# History logging
# ---------------------------------------------------------------------------


def test_history_logged_before_processing(client_query, user):
    """
    History entries are logged in a separate atomic block before processing.
    Even if processing fails unexpectedly, the history entry still exists and
    the mutation returns UNEXPECTED_ERROR (not a GraphQL-level error).
    """
    site_id = str(uuid.uuid4())
    entry = new_site_entry(site_id=site_id)

    with patch(
        "apps.project_management.graphql.site_push.SitePush._process_site_entry",
        side_effect=RuntimeError("Unexpected error"),
    ):
        response = client_query(
            PUSH_USER_DATA_QUERY,
            variables={"input": {"siteEntries": [entry]}},
        )

    # History entry should exist even though processing raised
    assert SitePushHistory.objects.filter(changed_by=user).exists()
    # Error is surfaced as a per-entry failure, not a GraphQL-level error
    results = get_site_results(response)
    assert results[0]["result"]["reason"] == "UNEXPECTED_ERROR"


# ---------------------------------------------------------------------------
# UserDataPush integration
# ---------------------------------------------------------------------------

PUSH_USER_DATA_SITES_AND_SOIL_QUERY = """
mutation pushUserData($input: UserDataPushInput!) {
  pushUserData(input: $input) {
    siteResults {
      siteId
      result {
        __typename
        ... on SitePushEntrySuccess {
          site { id name }
        }
        ... on SitePushEntryFailure {
          reason
        }
      }
    }
    soilDataResults {
      siteId
      result {
        __typename
        ... on SoilDataPushEntryFailure {
          reason
        }
      }
    }
  }
}
"""


def test_userdatapush_sites_only(client_query, user):
    site_id = str(uuid.uuid4())
    response = client_query(
        PUSH_USER_DATA_QUERY,
        variables={"input": {"siteEntries": [new_site_entry(site_id=site_id)]}},
    )
    content = json.loads(response.content)
    assert "errors" not in content, content.get("errors")
    assert content["data"]["pushUserData"]["siteResults"][0]["siteId"] == site_id


def test_userdatapush_sites_and_soil_data(client_query, user):
    """Sites + soil data in one request — both processed, site exists before soil refs it."""
    site_id = str(uuid.uuid4())
    # First create the site, then push both together
    site = Site.objects.create(id=site_id, name="Soil Site", latitude=0, longitude=0, owner=user)
    SoilData.objects.create(site=site)

    response = client_query(
        PUSH_USER_DATA_SITES_AND_SOIL_QUERY,
        variables={
            "input": {
                "siteEntries": [update_site_entry(site_id, name="Soil Site Renamed")],
                "soilDataEntries": [
                    {
                        "siteId": site_id,
                        "soilData": {
                            "depthDependentData": [],
                            "depthIntervals": [],
                            "deletedDepthIntervals": [],
                        },
                    }
                ],
            }
        },
    )
    content = json.loads(response.content)
    assert "errors" not in content, content.get("errors")
    assert (
        content["data"]["pushUserData"]["siteResults"][0]["result"]["__typename"]
        == "SitePushEntrySuccess"
    )
    assert (
        content["data"]["pushUserData"]["soilDataResults"][0]["result"]["__typename"]
        == "SoilDataPushEntrySuccess"
    )


PUSH_USER_DATA_WITH_ERRORS_QUERY = """
mutation pushUserData($input: UserDataPushInput!) {
  pushUserData(input: $input) {
    siteResults { siteId }
    errors
  }
}
"""


def test_userdatapush_requires_at_least_one_entry(client_query):
    """Empty input raises a validation error, surfaced as errors in the mutation payload."""
    response = client_query(
        PUSH_USER_DATA_WITH_ERRORS_QUERY,
        variables={"input": {}},
    )
    content = json.loads(response.content)
    # BaseMutation.mutate() catches exceptions and returns them as errors in the data payload
    assert content["data"]["pushUserData"]["errors"] is not None


# ---------------------------------------------------------------------------
# UNEXPECTED_ERROR handling
# ---------------------------------------------------------------------------

PUSH_USER_DATA_ALL_TYPES_QUERY = """
mutation pushUserData($input: UserDataPushInput!) {
  pushUserData(input: $input) {
    siteResults {
      siteId
      result {
        __typename
        ... on SitePushEntryFailure { reason }
        ... on SitePushEntrySuccess { site { id } }
      }
    }
    soilDataResults {
      siteId
      result {
        __typename
        ... on SoilDataPushEntryFailure { reason }
      }
    }
    soilMetadataResults {
      siteId
      result {
        __typename
        ... on SoilMetadataPushEntryFailure { reason }
      }
    }
  }
}
"""


def test_unexpected_error_returns_per_entry_failure_and_does_not_block_other_entries(
    client_query, user
):
    """
    An unexpected error on one entry is returned as UNEXPECTED_ERROR in that entry's
    result — not as a GraphQL-level error — and does not prevent other entries in the
    same request (including other sub-mutations) from being processed.
    """
    site_id = str(uuid.uuid4())
    site = Site.objects.create(id=site_id, name="S", latitude=0, longitude=0, owner=user)
    SoilData.objects.create(site=site)
    SoilMetadata.objects.create(site=site)

    with patch(
        "apps.project_management.graphql.site_push.SitePush._process_site_entry",
        side_effect=RuntimeError("simulated unexpected error"),
    ):
        response = client_query(
            PUSH_USER_DATA_ALL_TYPES_QUERY,
            variables={
                "input": {
                    "siteEntries": [update_site_entry(site_id)],
                    "soilDataEntries": [
                        {
                            "siteId": site_id,
                            "soilData": {
                                "depthDependentData": [],
                                "depthIntervals": [],
                                "deletedDepthIntervals": [],
                            },
                        }
                    ],
                    "soilMetadataEntries": [{"siteId": site_id, "userRatings": []}],
                }
            },
        )

    content = json.loads(response.content)
    assert "errors" not in content
    data = content["data"]["pushUserData"]
    assert data["siteResults"][0]["result"]["reason"] == "UNEXPECTED_ERROR"
    assert data["soilDataResults"][0]["result"]["__typename"] == "SoilDataPushEntrySuccess"
    assert data["soilMetadataResults"][0]["result"]["__typename"] == "SoilMetadataPushEntrySuccess"
