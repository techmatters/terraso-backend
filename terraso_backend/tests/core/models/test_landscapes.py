import math
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from mixer.backend.django import mixer

from apps.core.models.groups import Group, Membership
from apps.core.models.landscapes import Landscape, LandscapeGroup
from apps.core.models.users import User

pytestmark = pytest.mark.django_db


def test_landscape_string_format_is_its_name():
    landscape_name = "Landscape Model"
    landscape = mixer.blend(Landscape, name=landscape_name)

    assert landscape_name == str(landscape)


def test_landscape_is_slugifiable_by_name():
    landscape = mixer.blend(Landscape, name="This is My Name", slug=None)

    assert landscape.slug == "this-is-my-name"


def test_landscape_string_remove_spaces_from_name():
    landscape_name = "Terraso Landscape Name "
    landscape = mixer.blend(Landscape, name=landscape_name)

    assert landscape_name.strip() == str(landscape)


def test_landscape_string_remove_spaces_from_description():
    landscape_name = "Terraso Landscape Name"
    landscape_description = "Terraso Landscape Description "
    landscape = mixer.blend(Landscape, name=landscape_name)
    landscape.description = landscape_description
    landscape.save()

    assert landscape_description.strip() == landscape.description


def test_landscape_disallowed_name():
    landscape_name = "New"
    landscape = mixer.blend(Landscape, name=landscape_name)

    with pytest.raises(ValidationError, match="New is not allowed as a name"):
        landscape.full_clean()


def test_landscape_slug_is_updatable():
    landscape = mixer.blend(Landscape, name="This is My Name", slug=None)
    landscape.name = "New name"
    landscape.save()

    assert landscape.slug == "new-name"
    assert landscape.name == "New name"


def test_landscape_groups_are_created_when_association_added():
    landscape = mixer.blend(Landscape)
    groups = mixer.cycle(3).blend(Group)

    landscape.groups.add(*groups)

    assert landscape.associated_groups.count() == 3
    assert LandscapeGroup.objects.count() == 3


def test_landscape_groups_creation_explicitly():
    landscape = mixer.blend(Landscape)
    group = mixer.blend(Group)

    LandscapeGroup.objects.create(landscape=landscape, group=group)

    assert landscape.associated_groups.count() == 1
    assert group.associated_landscapes.count() == 1


def test_landscape_get_default_group():
    landscape = mixer.blend(Landscape)
    groups = mixer.cycle(3).blend(Group)
    default_group = groups.pop()

    LandscapeGroup.objects.create(
        landscape=landscape, group=default_group, is_default_landscape_group=True
    )
    landscape.groups.add(*groups)

    assert landscape.get_default_group() == default_group


def test_landscape_get_default_group_without_group_returns_none():
    landscape = mixer.blend(Landscape)

    assert landscape.get_default_group() is None


def test_landscape_creator_becomes_manager():
    user = mixer.blend(User)
    landscape = mixer.blend(Landscape, created_by=user)

    manager_membership = Membership.objects.get(group=landscape.get_default_group(), user=user)

    assert manager_membership.user_role == Membership.ROLE_MANAGER


def test_landscape_area_calculated(unit_polygon):
    area_polygon = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": unit_polygon}],
    }
    landscape = mixer.blend(Landscape, area_polygon=area_polygon)
    landscape.save()
    assert math.isclose(landscape.area_scalar_m2, 1, rel_tol=0.05)


def test_landscape_area_calculated_once(unit_polygon):
    area_polygon = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": unit_polygon}],
    }
    with patch(
        "apps.core.models.landscapes.calculate_geojson_feature_area", return_value=1
    ) as mock1:
        landscape = mixer.blend(Landscape, area_polygon=area_polygon)
    mock1.assert_called_once()
    landscape.name = "foo"
    with patch(
        "apps.core.models.landscapes.calculate_geojson_feature_area", return_value=1
    ) as mock2:
        landscape.save()
    mock2.assert_not_called()


def test_landscape_can_be_recreated_after_deletion():
    landscape = mixer.blend(Landscape)
    landscape.save()
    landscape.delete()
    new_landscape = mixer.blend(Landscape, name=landscape.name)
    new_landscape.save()
