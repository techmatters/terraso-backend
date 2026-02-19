# Copyright © 2021-2023 Technology Matters
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

import pytest
from mixer.backend.django import mixer

from apps.project_management.models import Site, SiteNote

pytestmark = pytest.mark.django_db


@pytest.fixture
def site(user):
    return Site.objects.create(
        name="Test Site", latitude=0, longitude=0, elevation=0, privacy="PUBLIC", owner=user
    )


@pytest.fixture
def site_note(user, site):
    return mixer.blend("project_management.SiteNote", author=user, site=site)


ADD_SITE_NOTE_QUERY = """
mutation addSiteNote($input: SiteNoteAddMutationInput!) {
  addSiteNote(input: $input) {
    siteNote {
      id
      content
      author {
        id
        firstName
        lastName
      }
      site {
        id
      }
    }
    errors
  }
}
"""


def site_note_creation_data(site):
    return {
        "content": "This is a test note.",
        "siteId": str(site.id),
    }


def test_site_note_creation(client_query, site, user):
    kwargs = site_note_creation_data(site)
    response = client_query(ADD_SITE_NOTE_QUERY, variables={"input": kwargs})
    content = json.loads(response.content)
    assert "errors" not in content, content["errors"]
    id = content["data"]["addSiteNote"]["siteNote"]["id"]
    site_note = SiteNote.objects.get(pk=id)
    assert str(site_note.id) == id
    assert site_note.content == "This is a test note."
    assert site_note.author == user
    assert site_note.site == site


def test_site_note_creation_unauthorized(client_query, project_site):
    kwargs = site_note_creation_data(project_site)
    response = client_query(ADD_SITE_NOTE_QUERY, variables={"input": kwargs})
    content = json.loads(response.content)
    assert "errors" in content, content["errors"]


def test_site_note_creation_with_client_id(client_query, site, user):
    client_id = str(uuid.uuid4())
    kwargs = site_note_creation_data(site)
    kwargs["id"] = client_id
    response = client_query(ADD_SITE_NOTE_QUERY, variables={"input": kwargs})
    content = json.loads(response.content)
    assert "errors" not in content, content["errors"]
    id = content["data"]["addSiteNote"]["siteNote"]["id"]
    assert id == client_id
    site_note = SiteNote.objects.get(pk=client_id)
    assert str(site_note.id) == client_id
    assert site_note.author == user


def test_site_note_creation_without_client_id_backwards_compat(client_query, site, user):
    kwargs = site_note_creation_data(site)
    response = client_query(ADD_SITE_NOTE_QUERY, variables={"input": kwargs})
    content = json.loads(response.content)
    assert "errors" not in content, content["errors"]
    id = content["data"]["addSiteNote"]["siteNote"]["id"]
    site_note = SiteNote.objects.get(pk=id)
    assert str(site_note.id) == id
    assert site_note.author == user


def test_site_note_creation_duplicate_client_id_returns_existing(client_query, site, user):
    client_id = str(uuid.uuid4())
    kwargs = site_note_creation_data(site)
    kwargs["id"] = client_id

    response1 = client_query(ADD_SITE_NOTE_QUERY, variables={"input": kwargs})
    content1 = json.loads(response1.content)
    assert "errors" not in content1, content1["errors"]

    response2 = client_query(ADD_SITE_NOTE_QUERY, variables={"input": kwargs})
    content2 = json.loads(response2.content)
    assert "errors" not in content2, content2["errors"]

    assert (
        content1["data"]["addSiteNote"]["siteNote"]["id"]
        == content2["data"]["addSiteNote"]["siteNote"]["id"]
    )
    assert SiteNote.objects.filter(pk=client_id).count() == 1


def test_site_note_creation_invalid_client_id_rejected(client_query, site, user):
    kwargs = site_note_creation_data(site)
    kwargs["id"] = "not-a-valid-uuid"
    initial_count = SiteNote.objects.count()
    response = client_query(ADD_SITE_NOTE_QUERY, variables={"input": kwargs})
    content = json.loads(response.content)
    assert "errors" in content
    assert SiteNote.objects.count() == initial_count


DELETE_SITE_NOTE_QUERY = """
    mutation deleteSiteNote($input: SiteNoteDeleteMutationInput!) {
        deleteSiteNote(input: $input) {
            errors
        }
    }
"""


def test_delete_site_note(client_query, site_note):
    response = client_query(DELETE_SITE_NOTE_QUERY, variables={"input": {"id": str(site_note.id)}})
    assert response.json()["data"]["deleteSiteNote"]["errors"] is None
    assert len(SiteNote.objects.filter(id=site_note.id)) == 0


def test_delete_site_note_unauthorized(client_query, project_site, project_user):
    site_note = mixer.blend(SiteNote, author=project_user, site=project_site)
    client_query(DELETE_SITE_NOTE_QUERY, variables={"input": {"id": str(site_note.id)}})

    assert len(SiteNote.objects.filter(id=site_note.id)) == 1


UPDATE_SITE_NOTE_QUERY = """
mutation updateSiteNote($input: SiteNoteUpdateMutationInput!) {
  updateSiteNote(input: $input) {
    siteNote {
      id
      content
      author {
        id
        firstName
        lastName
      }
      site {
        id
      }
      createdAt
      updatedAt
    }
    errors
  }
}
"""


def test_site_note_update(client_query, client, site_note):
    variables = {"input": {"id": str(site_note.id), "content": "This is an updated test note."}}
    response = client_query(UPDATE_SITE_NOTE_QUERY, variables=variables)
    content = json.loads(response.content)
    assert "errors" not in content, f"Unexpected errors: {content.get('errors')}"
    site_note.refresh_from_db()
    assert site_note.content == "This is an updated test note.", (
        "Site note content did not update as expected"
    )


def test_site_note_update_unauthorized(client_query, project_site, project_user):
    site_note = mixer.blend(SiteNote, author=project_user, site=project_site)
    variables = {"input": {"id": str(site_note.id), "content": "This is an updated test note."}}
    client_query(UPDATE_SITE_NOTE_QUERY, variables=variables)

    site_note.refresh_from_db()
    assert site_note.content != "This is an updated test note.", (
        "Site note content updated unexpectedly"
    )
