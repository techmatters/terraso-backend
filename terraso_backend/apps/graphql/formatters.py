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
