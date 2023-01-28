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

from dataclasses import dataclass

from .formatters import from_snake_to_camel_case


@dataclass
class ErrorContext:
    model: str
    field: str
    extra: str = ""

    def __post_init__(self):
        self.field = from_snake_to_camel_case(self.field) if self.field else self.field


@dataclass
class ErrorMessage:
    code: str
    context: ErrorContext
