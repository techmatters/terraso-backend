class GraphQLValidationException(Exception):
    @classmethod
    def from_validation_error(cls, validation_error):
        messages = []

        for field, validation_errors in validation_error.error_dict.items():
            for error in validation_errors:
                messages.extend([f"field={field}, error={message}" for message in error.messages])

        error_message = ";".join(messages)

        return cls(error_message)
