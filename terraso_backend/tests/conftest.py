import pytest
from django.test.client import Client
from mixer.backend.django import mixer
from pyproj import CRS, Transformer

from apps.auth.services import JWTService
from apps.core.geo import DEFAULT_CRS
from apps.core.models import User

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
