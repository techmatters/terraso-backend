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
"""SiteNote.author preservation across user soft-delete / undelete.

A note authored on someone else's site survives the author's deletion with a
null author; if the author is undeleted before hard-delete, the author is
restored from the `saved_author` shadow. After hard-delete it is gone for good.
"""

import pytest
from safedelete.config import HARD_DELETE

from apps.core.models import User
from apps.project_management.models import Site, SiteNote

pytestmark = pytest.mark.django_db


def _user(email, **kw):
    return User.objects.create_user(email, first_name="F", last_name="L", **kw)


def test_author_saved_on_soft_delete_and_restored_on_undelete():
    author = _user("author@example.com")
    owner = _user("owner@example.com")
    site = Site.objects.create(name="host", owner=owner, latitude=0, longitude=0)
    note = SiteNote.objects.create(site=site, content="c", author=author)

    author.delete()
    note.refresh_from_db()
    assert note.author_id is None, "author should be nulled so the note survives"
    assert note.saved_author == author.id, "author id should be stashed"

    author.undelete()
    note.refresh_from_db()
    assert note.author_id == author.id, "author should be restored on undelete"
    assert note.saved_author is None, "shadow should be cleared after restore"


def test_note_on_authors_own_site_is_restored_too():
    # The author owns the site: the site soft-deletes with the user, the note
    # soft-deletes with the site, and the author is nulled. Undelete must bring
    # back the note AND its author.
    author = _user("solo@example.com")
    site = Site.objects.create(name="own", owner=author, latitude=0, longitude=0)
    note = SiteNote.objects.create(site=site, content="c", author=author)

    author.delete()
    saved = SiteNote.all_objects.get(id=note.id)
    assert saved.deleted_at is not None
    assert saved.author_id is None
    assert saved.saved_author == author.id

    author.undelete()
    restored = SiteNote.all_objects.get(id=note.id)
    assert restored.deleted_at is None
    assert restored.author_id == author.id
    assert restored.saved_author is None


def test_author_gone_permanently_after_hard_delete():
    author = _user("author@example.com")
    owner = _user("owner@example.com")
    site = Site.objects.create(name="host", owner=owner, latitude=0, longitude=0)
    note = SiteNote.objects.create(site=site, content="c", author=author)

    author.delete()
    author.delete(force_policy=HARD_DELETE)

    note.refresh_from_db()
    assert note.author_id is None
    assert not User.all_objects.filter(id=author.id).exists()
