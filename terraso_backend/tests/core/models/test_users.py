import pytest
from mixer.backend.django import mixer

from apps.core.models import Group, Landscape, LandscapeGroup, User

pytestmark = pytest.mark.django_db


def test_user_string_format_is_its_email():
    user_email = "test@example.com"
    user = mixer.blend(User, email=user_email)

    assert user_email == str(user)


@pytest.mark.parametrize(
    "is_default_landscape_group, is_expected_to_be_manager",
    (
        (True, True),
        (False, False),
    ),
)
def test_user_is_landscape_manager(is_default_landscape_group, is_expected_to_be_manager):
    user = mixer.blend(User)
    group = mixer.blend(Group)
    landscape = mixer.blend(Landscape)
    mixer.blend(
        LandscapeGroup,
        landscape=landscape,
        group=group,
        is_default_landscape_group=is_default_landscape_group,
    )
    group.add_manager(user)

    assert user.is_landscape_manager(landscape.id) is is_expected_to_be_manager
