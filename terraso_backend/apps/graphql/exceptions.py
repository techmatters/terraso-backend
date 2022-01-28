class GraphQLValidationException(Exception):
    @classmethod
    def from_validation_error(cls, validation_error):
        messages = []

        for field, validation_errors in validation_error.error_dict.items():
            for error in validation_errors:
                messages.append(_format_error_message(field, error.code))

        error_message = "; ".join(messages)

        return cls(error_message)


class GraphQLNotFoundException(GraphQLValidationException):
    def __init__(self, message="", field=None):
        super().__init__(_format_error_message(field, "not_found", extra=message))


class GraphQLNotAllowedException(GraphQLValidationException):
    def __init__(self, message="", field=None, operation="operation"):
        super().__init__(_format_error_message(field, f"{operation}_not_allowed", extra=message))


def _format_error_message(field, error_code, extra=""):
    if extra:
        return f"field={field}, error_code={error_code}, message={extra}"
    return f"field={field}, error_code={error_code}"
