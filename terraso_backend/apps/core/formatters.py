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

import re

RE_CAMEL_TO_SNAKE_CASE = re.compile(r"(?<!^)(?=[A-Z])")


def from_camel_to_snake_case(camel_case_string):
    """
    Transforms camel case to snake case. MyModel becomes my_model.
    """
    return RE_CAMEL_TO_SNAKE_CASE.sub("_", camel_case_string).lower()


def from_snake_to_camel_case(snake_case_string):
    """
    Transforms camel case to snake case. my_field_name becomes myFieldName.
    """
    if not snake_case_string:
        return ""

    words = snake_case_string.split("_")
    return words[0].lower() + "".join([w.lower().title() for w in words[1:]])
