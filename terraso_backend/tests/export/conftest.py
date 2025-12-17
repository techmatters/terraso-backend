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

import pytest
from mixer.backend.django import mixer

from apps.collaboration.models import Membership
from apps.export.fetch_data import clear_soil_id_cache
from apps.export.models import ExportToken
from apps.project_management.models import Project, Site

pytestmark = pytest.mark.django_db


# Note: These fixtures use users[0] and users[1] from the global conftest.py.
# Similar fixtures exist in tests/graphql/mutations/test_export_tokens.py
# which use the `user` fixture for GraphQL authentication context.


@pytest.fixture
def export_user(users):
    """Primary user for export tests (users[0])."""
    return users[0]


@pytest.fixture
def export_user_2(users):
    """Secondary user for export tests (users[1])."""
    return users[1]


@pytest.fixture
def owned_site(export_user):
    """Site owned by export_user (not in any project)."""
    return mixer.blend(
        Site,
        owner=export_user,
        name="Test Owned Site",
        latitude=40.0,
        longitude=-105.0,
        elevation=1600.0,
    )


@pytest.fixture
def unicode_site(export_user):
    """Site with Unicode characters in name."""
    return mixer.blend(
        Site,
        owner=export_user,
        name="Test Сайт 测试 Site",  # Ukrainian + Mandarin
        latitude=41.0,
        longitude=-106.0,
        elevation=1700.0,
    )


@pytest.fixture
def export_project(export_user_2):
    """Project owned by export_user_2."""
    project = mixer.blend(Project, name="Test Export Project")
    project.add_manager(export_user_2)
    return project


@pytest.fixture
def project_with_member(export_project, export_user):
    """Project with export_user added as a viewer."""
    Membership.objects.create(
        user=export_user,
        membership_list=export_project.membership_list,
        user_role="VIEWER",
        membership_status=Membership.APPROVED,
    )
    return export_project


@pytest.fixture
def project_site(export_project):
    """Site belonging to a project."""
    return mixer.blend(
        Site,
        project=export_project,
        owner=None,
        name="Project Site 1",
        latitude=42.0,
        longitude=-107.0,
        elevation=1800.0,
    )


# Export token fixtures


@pytest.fixture
def site_export_token(owned_site, export_user):
    """Export token for a single site."""
    return ExportToken.create_token("SITE", str(owned_site.id), str(export_user.id))


@pytest.fixture
def project_export_token(export_project, export_user_2):
    """Export token for a project."""
    return ExportToken.create_token("PROJECT", str(export_project.id), str(export_user_2.id))


@pytest.fixture
def user_export_token(export_user):
    """Export token for user's sites."""
    return ExportToken.create_token("USER", str(export_user.id), str(export_user.id))


@pytest.fixture(autouse=True)
def clear_soil_id_cache_after_test():
    """Clear the soil_id cache after each test to ensure isolation.

    This runs automatically for every test in this directory (autouse=True).
    The cache is populated by fixture_loader when loading raw.json fixtures,
    allowing tests to skip external soil API calls.
    """
    yield
    clear_soil_id_cache()
