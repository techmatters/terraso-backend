import json
from dataclasses import asdict, dataclass

from .formatters import from_snake_to_camel_case


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
