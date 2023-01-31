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

import pytest

from apps.core.formatters import from_camel_to_snake_case, from_snake_to_camel_case


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
