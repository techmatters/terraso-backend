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
    Each token maps to a specific resource (User, Project, or Site).
    """

    RESOURCE_TYPES = [
        ("USER", "User"),
        ("PROJECT", "Project"),
        ("SITE", "Site"),
    ]

    token = models.CharField(max_length=36, primary_key=True)  # UUID4 is 36 chars
    resource_type = models.CharField(max_length=10, choices=RESOURCE_TYPES)
    resource_id = models.CharField(max_length=255)

    class Meta:
        db_table = "export_token"
        indexes = [
            models.Index(fields=["resource_type", "resource_id"]),
        ]

    @classmethod
    def create_token(cls, resource_type, resource_id):
        """Create a new export token for a resource."""
        token = str(uuid.uuid4())
        return cls.objects.create(
            token=token, resource_type=resource_type, resource_id=resource_id
        )

    def __str__(self):
        return f"{self.resource_type}:{self.resource_id} -> {self.token}"
