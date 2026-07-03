# Copyright © 2023 Technology Matters
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

from django.db import models

from apps.core.models import User
from apps.core.models.commons import BaseModel


class SiteNote(BaseModel):
    class Meta(BaseModel.Meta):
        abstract = False

    site = models.ForeignKey("Site", on_delete=models.CASCADE, related_name="notes")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="author of the note",
    )
    # Preserves the author's user id while their account is soft-deleted so
    # User.undelete() can restore `author`. Deliberately NOT a ForeignKey: it
    # must survive the author's soft-delete (whose SET_NULL cascade blanks
    # `author`) and their hard-delete without a dangling constraint. Set by
    # User._soft_delete_with_cascade, cleared by User.undelete.
    saved_author = models.UUIDField(null=True, blank=True, editable=False)

    def is_author(self, user: User) -> bool:
        return self.author == user
