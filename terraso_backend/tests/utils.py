import re

from jsonpath_ng import parse as jsonpath_parse


def match_json(match_expression, dictionary):
    return [match.value for match in jsonpath_parse(match_expression).find(dictionary)]


def to_snake_case(name):
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub("__([A-Z])", r"_\1", name)
    name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()
