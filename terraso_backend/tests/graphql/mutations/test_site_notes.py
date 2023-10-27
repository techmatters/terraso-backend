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

import pytest
from graphene_django.utils.testing import graphql_query
from mixer.backend.django import mixer

from apps.project_management.models import Site, SiteNote

pytestmark = pytest.mark.django_db


@pytest.fixture
def site(user):
    return Site.objects.create(
        name="Test Site", latitude=0, longitude=0, privacy="PUBLIC", owner=user
    )


@pytest.fixture
def site_note(user, site):
    return mixer.blend("project_management.SiteNote", author=user, site=site)


CREATE_SITE_NOTE_QUERY = """
mutation createSiteNote($input: SiteNoteAddMutationInput!) {
  createSiteNote(input: $input) {
    siteNote {
      id
      content
      author {
        id
        username
      }
      site {
        id
      }
    }
    errors
  }
}
"""


def site_note_creation_data():
    return {"content": "This is a test note."}


def test_site_note_creation(client_query, site, user):
    kwargs = site_note_creation_data()
    response = client_query(CREATE_SITE_NOTE_QUERY, variables={"input": kwargs})
    content = json.loads(response.content)
    assert "errors" not in content
    id = content["data"]["addSiteNote"]["siteNote"]["id"]
    site_note = SiteNote.objects.get(pk=id)
    assert str(site_note.id) == id
    assert site_note.content == "This is a test note."
    assert site_note.author == user
    assert site_note.site == site


DELETE_SITE_NOTE_QUERY = """
    mutation deleteSiteNote($input: SiteNoteDeleteMutationInput!) {
        deleteSiteNote(input: $input) {
            errors
        }
    }
"""


def test_delete_site_note(client, site_note, site_note_author):
    client.force_login(site_note_author)

    response = graphql_query(
        DELETE_SITE_NOTE_QUERY,
        variables={"input": {"id": str(site_note.id)}},
        client=client,
    )
    assert response.json()["data"]["deleteSiteNote"]["errors"] is None
    assert len(SiteNote.objects.filter(id=site_note.id)) == 0


UPDATE_SITE_NOTE_QUERY = """
mutation updateSiteNote($input: SiteNoteUpdateMutationInput!) {
  updateSiteNote(input: $input) {
    siteNote {
      id
      content
      author {
        id
        username
      }
      site {
        id
      }
      createdAt
      updatedAt
    }
    errors {
      field
      messages
    }
  }
}
"""


def test_site_note_update(client, site_note):
    response = graphql_query(
        UPDATE_SITE_NOTE_QUERY,
        variables={"input": {"id": str(site_note.id), "content": "This is an updated test note."}},
        client=client,
    )
    content = json.loads(response.content)

    assert "errors" not in content
    site_note.refresh_from_db()

    assert site_note.content == "This is an updated test note."
