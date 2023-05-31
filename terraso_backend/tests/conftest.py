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
from apps.core.gis.utils import DEFAULT_CRS
from apps.core.models import User
from apps.project_management.models import Project, Site

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
def site_creator(site: Site) -> User:
    return site.owner


@pytest.fixture
def project() -> Project:
    group = Project.create_default_group("test_group")
    project = mixer.blend(Project, group=group)
    user = mixer.blend(User)
    project.add_manager(user)
    return project


@pytest.fixture
def project_manager(project: Project) -> User:
    return project.managers.first()
