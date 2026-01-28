# Copyright © 2021-2025 Technology Matters
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
import re

from django.conf import settings
from django.dispatch import receiver
from django_structlog import signals


def _get_log_level():
    """Read GRAPHQL_LOG_LEVEL at call time so code changes take effect on hot reload."""
    if getattr(settings, "ENV", "") != "development":
        return "minimal"
    return getattr(settings, "GRAPHQL_LOG_LEVEL", "names")


def _is_graphql_request(request):
    return request.method == "POST" and request.path.rstrip("/").endswith("/graphql")


def _parse_graphql_body(request):
    """Parse GraphQL request body, returning (query_string, variables) or (None, None)."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return None, None

    query = body.get("query")
    variables = body.get("variables")
    return query, variables


# Matches named operations like "query getSites" or "mutation updateUser" and captures the name.
# Example: "query getSites { ... }" -> captures "getSites"
_OPERATION_RE = re.compile(r"^\s*(?:query|mutation|subscription)\s+(\w+)", re.MULTILINE)

# Matches the operation type keyword (query/mutation/subscription) to determine the operation type.
# Used for both named and anonymous operations.
_OPERATION_TYPE_RE = re.compile(r"^\s*(query|mutation|subscription)\b", re.MULTILINE)

# Matches field names followed by arguments or selection sets: "fieldName(" or "fieldName{".
# Used to extract top-level fields from anonymous queries for logging context.
_TOP_LEVEL_FIELDS_RE = re.compile(r"(\w+)\s*[\({]", re.MULTILINE)


def _extract_top_level_fields(query):
    """Extract top-level field names from a GraphQL query body (the part after the first '{')."""
    brace_pos = query.find("{")
    if brace_pos == -1:
        return []
    body = query[brace_pos + 1 :]
    fields = []
    for match in _TOP_LEVEL_FIELDS_RE.finditer(body):
        # Count braces before this match to determine depth
        preceding = body[: match.start()]
        depth = preceding.count("{") - preceding.count("}")
        if depth == 0:
            fields.append(match.group(1))
    return fields[:5]


def _extract_operation_name(query):
    """Extract a human-readable operation description from a GraphQL query string.

    Returns strings like:
        "userSoilData (query)"
        "updateSite (mutation)"
        "Anonymous: [sites, users] (query)"
    """
    if not query:
        return None

    match = _OPERATION_RE.search(query)
    if match:
        name = match.group(1)
        type_match = _OPERATION_TYPE_RE.search(query)
        op_type = type_match.group(1) if type_match else "query"
        return f"{name} ({op_type})"

    type_match = _OPERATION_TYPE_RE.search(query)
    op_type = type_match.group(1) if type_match else "query"
    fields = _extract_top_level_fields(query)
    if fields:
        field_list = ", ".join(fields)
        return f"Anonymous: [{field_list}] ({op_type})"

    return f"Anonymous ({op_type})"


@receiver(signals.bind_extra_request_metadata)
def add_graphql_request_info(request, logger, log_kwargs, **kwargs):
    """Enrich 'request_started' log with GraphQL operation name and variables."""
    log_level = _get_log_level()
    if log_level == "minimal" or not _is_graphql_request(request):
        return

    query, variables = _parse_graphql_body(request)
    operation = _extract_operation_name(query)
    if operation:
        log_kwargs["graphql_operation"] = operation

    if log_level == "full" and variables:
        log_kwargs["graphql_variables"] = variables


@receiver(signals.bind_extra_request_finished_metadata)
def add_graphql_response_info(request, logger, response, log_kwargs, **kwargs):
    """Enrich 'request_finished' log with GraphQL operation name, error flag, and response."""
    log_level = _get_log_level()
    if log_level == "minimal" or not _is_graphql_request(request):
        return

    query, _ = _parse_graphql_body(request)
    operation = _extract_operation_name(query)
    if operation:
        log_kwargs["graphql_operation"] = operation

    try:
        response_data = json.loads(response.content)
    except (json.JSONDecodeError, ValueError, AttributeError):
        response_data = None

    if response_data and "errors" in response_data:
        log_kwargs["graphql_has_errors"] = True

    if log_level == "full" and response_data is not None:
        log_kwargs["graphql_response"] = response_data


@receiver(signals.bind_extra_request_failed_metadata)
def add_graphql_error_info(request, logger, exception, log_kwargs, **kwargs):
    """Enrich 'request_failed' log with GraphQL operation name and variables.
    This is rare, as it only happens with unhandled exceptions, and graphene catches exceptions and converts them to errors in the response body."""
    log_level = _get_log_level()
    if log_level == "minimal" or not _is_graphql_request(request):
        return

    query, variables = _parse_graphql_body(request)
    operation = _extract_operation_name(query)
    if operation:
        log_kwargs["graphql_operation"] = operation

    if log_level == "full" and variables:
        log_kwargs["graphql_variables"] = variables
