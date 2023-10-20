from jsonpath_ng import parse as jsonpath_parse


def match_json(match_expression, dictionary):
    return [match.value for match in jsonpath_parse(match_expression).find(dictionary)]
