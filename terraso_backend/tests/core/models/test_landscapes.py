import pytest
from mixer.backend.django import mixer

from apps.core.models.groups import Group
from apps.core.models.landscapes import Landscape, LandscapeGroup

pytestmark = pytest.mark.django_db


def test_landscape_string_format_is_its_name():
    landscape_name = "Landscape Model"
    landscape = mixer.blend(Landscape, name=landscape_name)

    assert landscape_name == str(landscape)


def test_landscape_is_slugifiable_by_name():
    landscape = mixer.blend(Landscape, name="This is My Name", slug=None)

    assert landscape.slug == "this-is-my-name"


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
