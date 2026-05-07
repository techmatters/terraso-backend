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

"""Regression tests for the export-token cleanup signals."""

import pytest
from mixer.backend.django import mixer

from apps.core.models import User
from apps.export.models import ExportToken
from apps.project_management.models import Project, Site

pytestmark = pytest.mark.django_db


def test_membership_removal_triggers_export_token_cleanup():
    """The post_save handler in apps/export/signals.py uses
    project.site_set (the Django default reverse manager). An earlier
    bug used project.sites which raised AttributeError on every
    project-membership soft-delete and silently broke token cleanup."""
    user = mixer.blend(User)
    project = mixer.blend(Project)
    project.add_manager(user)
    site = mixer.blend(Site, project=project, owner=None)

    site_token = ExportToken.create_token("SITE", str(site.id), str(user.id))
    project_token = ExportToken.create_token("PROJECT", str(project.id), str(user.id))

    membership = project.membership_list.memberships.get(user=user)
    membership.delete()  # cascades through SafeDeleteModel post_save

    # Both tokens should now be revoked.
    assert not ExportToken.objects.filter(token=site_token.token).exists()
    assert not ExportToken.objects.filter(token=project_token.token).exists()
