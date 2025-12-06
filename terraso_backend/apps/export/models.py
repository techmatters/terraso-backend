# Copyright © 2021-2025 Technology Matters
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

import uuid

from django.db import models


class ExportToken(models.Model):
    """
    Export tokens provide secure, shareable access to export endpoints.
    Each token maps to a specific user-resource pair, allowing multiple users
    to have their own tokens for the same resource.
    """

    RESOURCE_TYPES = [
        ("USER", "User"),
        ("PROJECT", "Project"),
        ("SITE", "Site"),
    ]

    token = models.CharField(max_length=36, primary_key=True)  # UUID4 is 36 chars
    resource_type = models.CharField(max_length=10, choices=RESOURCE_TYPES)
    resource_id = models.CharField(max_length=255)
    user_id = models.CharField(max_length=255)  # User who created the token

    class Meta:
        db_table = "export_token"
        indexes = [
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["user_id", "resource_type", "resource_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "resource_type", "resource_id"],
                name="unique_user_resource_token",
            )
        ]

    @classmethod
    def create_token(cls, resource_type, resource_id, user_id):
        """Create a new export token for a user-resource pair."""
        token = str(uuid.uuid4())
        return cls.objects.create(
            token=token,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
        )

    @classmethod
    def get_or_create_token(cls, resource_type, resource_id, user_id):
        """Get existing token or create new one for user-resource pair."""
        token_obj, created = cls.objects.get_or_create(
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            defaults={"token": str(uuid.uuid4())},
        )
        return token_obj, created

    def __str__(self):
        return f"User {self.user_id} -> {self.resource_type}:{self.resource_id} ({self.token})"
