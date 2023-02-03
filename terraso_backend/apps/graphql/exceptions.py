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
from dataclasses import asdict

from apps.core.exceptions import ErrorContext, ErrorMessage


class GraphQLValidationException(Exception):
    def __init__(self, message="", error_messages=None):
        if error_messages:
            super().__init__(json.dumps([asdict(e) for e in error_messages]))
        else:
            super().__init__(message)

    @classmethod
    def from_validation_error(cls, validation_error, model_name=""):
        error_messages = []
        for field, validation_errors in validation_error.error_dict.items():
            for error in validation_errors:
                error_messages.append(
                    ErrorMessage(
                        code=error.code,
                        context=ErrorContext(model=model_name, field=field),
                    )
                )

        return cls(error_messages=error_messages)


class GraphQLNotFoundException(GraphQLValidationException):
    def __init__(self, message="", field=None, model_name=None):
        error_message = ErrorMessage(
            code="not_found", context=ErrorContext(model=model_name, field=field)
        )
        super().__init__(error_messages=[error_message])


class GraphQLNotAllowedException(GraphQLValidationException):
    def __init__(self, message="", field=None, model_name=None, operation="operation"):
        operation_name = f"{operation}_not_allowed"

        error_message = ErrorMessage(
            code=operation_name, context=ErrorContext(model=model_name, field=field, extra=message)
        )
        super().__init__(error_messages=[error_message])
