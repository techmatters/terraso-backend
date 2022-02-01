import pytest

from apps.graphql.formatters import from_camel_to_snake_case, from_snake_to_camel_case


@pytest.mark.parametrize(
    "camel_case, snake_case",
    (
        ("field", "field"),
        ("fieldName", "field_name"),
        ("multiPartFieldName", "multi_part_field_name"),
    ),
)
def test_camel_to_snake(camel_case, snake_case):
    assert from_camel_to_snake_case(camel_case) == snake_case


@pytest.mark.parametrize(
    "snake_case, camel_case",
    (
        ("field", "field"),
        ("field_name", "fieldName"),
        ("multi_part_field_name", "multiPartFieldName"),
        ("uNusuAl_FiEld_nAMe", "unusualFieldName"),
    ),
)
def test_snake_to_camel(snake_case, camel_case):
    assert from_snake_to_camel_case(snake_case) == camel_case
