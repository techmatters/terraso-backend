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
from importlib import resources

import pytest
from django.test.client import Client
from mixer.backend.django import mixer
from pyproj import CRS, Transformer

from apps.auth.services import JWTService
from apps.collaboration.models import Membership
from apps.core.gis.utils import DEFAULT_CRS
from apps.core.models import User
from apps.project_management.models import Project, Site
from apps.soil_id.models import (
    DepthDependentSoilData,
    LandPKSIntervalDefaults,
    ProjectSoilSettings,
    SoilData,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def users():
    return mixer.cycle(5).blend(User)


@pytest.fixture
def access_token(users):
    return JWTService().create_access_token(users[0])


@pytest.fixture
def logged_client(access_token):
    return Client(HTTP_AUTHORIZATION=f"Bearer {access_token}")


@pytest.fixture
def unit_polygon():
    """A polygon whose geographical area is roughly 1 km squared."""
    center_x, center_y = (1281904.47, 8752400.16)
    xs = [center_x + delta for delta in [0, 0, 1, 1, 0]]
    ys = [center_y + delta for delta in [0, 1, 1, 0, 0]]
    # UTM zone 32S, chosen at random
    source_crs = CRS.from_epsg(9156)
    # Web Mercator
    target_crs = DEFAULT_CRS
    proj = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    x_degrees, y_degrees = proj.transform(xs, ys)
    geojson = {
        "type": "Polygon",
        "coordinates": [
            list(zip(x_degrees, y_degrees)),
        ],
    }
    return geojson


@pytest.fixture
def usa_geojson():
    """Loads a geojson file containing the boundary of the United States of America"""
    file_path = resources.files("tests").joinpath("resources/usa.json")
    with open(file_path) as fp:
        return json.load(fp)


@pytest.fixture
def site(user: User) -> Site:
    """Sample site created by user fixture"""
    return mixer.blend(Site, owner=user)


@pytest.fixture
def archived_site(user: User) -> Site:
    return mixer.blend(Site, owner=user, archived=True)


@pytest.fixture
def site_creator(site: Site) -> User:
    return site.owner


@pytest.fixture
def project() -> Project:
    project = mixer.blend(Project)
    user = mixer.blend(User)
    project.add_manager(user)
    return project


@pytest.fixture
def project_manager(project: Project) -> User:
    return project.manager_memberships.first().user


@pytest.fixture
def project_with_sites(project: Project) -> Project:
    mixer.blend(Site, project=project)
    return project


@pytest.fixture
def project_site(project: Project) -> Site:
    return mixer.blend(Site, project=project)


@pytest.fixture
def project_user(project: Project) -> User:
    user = mixer.blend(User)
    Membership.objects.create(
        user=user,
        membership_list=project.membership_list,
        user_role="viewer",
        membership_status=Membership.APPROVED,
    )
    return user


@pytest.fixture
def project_user_w_role(request, project: Project):
    user = mixer.blend(User)
    project.add_user_with_role(user, request.param)
    return user


@pytest.fixture
def site_with_soil_data(request, project_manager: User, project: Project, project_site: Site):
    ProjectSoilSettings.objects.create(project=project)
    SoilData.objects.create(site=project_site)
    for interval in LandPKSIntervalDefaults:
        DepthDependentSoilData.objects.create(
            soil_data=project_site.soil_data,
            depth_interval_start=interval["depth_interval_start"],
            depth_interval_end=interval["depth_interval_end"],
        )
    return project_site


@pytest.fixture
def site_with_soil_data_or_not(request, project_site, site_with_soil_data):
    """This fixture is for indirect parametrization, when we want to test with both a
    site that has soil data, and one that does not.

    Usage:

    @pytest.mark.parametrize("site_with_soil_data_or_not", [False, True], indirect=True)
    def test_sites(site_with_soil_data_or_not):
        ...
    """
    if not request:
        return (False, project_site)
    return (True, site_with_soil_data)
