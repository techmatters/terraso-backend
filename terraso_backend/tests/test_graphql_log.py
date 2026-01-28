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

import pytest
from config.graphql_log import (
    _extract_operation_name,
    add_graphql_error_info,
    add_graphql_request_info,
    add_graphql_response_info,
)
from django.test import RequestFactory, override_settings

# NOTE: This tests the graphql info displayed in development-only console logs, so it should not be relevant for product code


@pytest.mark.unit
class TestExtractOperationName:
    def test_named_query(self):
        assert (
            _extract_operation_name("query userSoilData { soil { id } }") == "userSoilData (query)"
        )

    def test_named_mutation(self):
        query = "mutation updateSite($input: Input!) { updateSite(input: $input) { id } }"
        assert _extract_operation_name(query) == "updateSite (mutation)"

    def test_named_subscription(self):
        assert (
            _extract_operation_name("subscription onUpdate { updated { id } }")
            == "onUpdate (subscription)"
        )

    def test_anonymous_query_with_fields(self):
        assert (
            _extract_operation_name("{ sites { id } users { name } }")
            == "Anonymous: [sites, users] (query)"
        )

    def test_anonymous_explicit_query(self):
        assert _extract_operation_name("query { sites { id } }") == "Anonymous: [sites] (query)"

    def test_empty_query(self):
        assert _extract_operation_name("") is None
        assert _extract_operation_name(None) is None

    def test_multiline_query(self):
        query = """
        query getSiteData($id: ID!) {
            site(id: $id) {
                name
            }
        }
        """
        assert _extract_operation_name(query) == "getSiteData (query)"


def _make_graphql_request(body):
    factory = RequestFactory()
    return factory.post(
        "/graphql/",
        data=json.dumps(body),
        content_type="application/json",
    )


# These handlers are called by django_structlog signals:
# - add_graphql_request_info  -> bind_extra_request_metadata    -> enriches "request_started" log
# - add_graphql_response_info -> bind_extra_request_finished_metadata -> enriches "request_finished" log
# - add_graphql_error_info    -> bind_extra_request_failed_metadata   -> enriches "request_failed" log


@pytest.mark.unit
class TestAddGraphqlRequestInfo:
    @override_settings(ENV="development", GRAPHQL_LOG_LEVEL="names")
    def test_names_adds_operation(self):
        request = _make_graphql_request({"query": "query getSites { sites { id } }"})
        log_kwargs = {}
        add_graphql_request_info(request=request, logger=None, log_kwargs=log_kwargs, sender=None)
        assert log_kwargs["graphql_operation"] == "getSites (query)"
        assert "graphql_variables" not in log_kwargs

    @override_settings(ENV="development", GRAPHQL_LOG_LEVEL="full")
    def test_full_adds_variables(self):
        request = _make_graphql_request(
            {
                "query": "mutation updateSite($id: ID!) { updateSite(id: $id) { id } }",
                "variables": {"id": "123"},
            }
        )
        log_kwargs = {}
        add_graphql_request_info(request=request, logger=None, log_kwargs=log_kwargs, sender=None)
        assert log_kwargs["graphql_operation"] == "updateSite (mutation)"
        assert log_kwargs["graphql_variables"] == {"id": "123"}

    @override_settings(ENV="development", GRAPHQL_LOG_LEVEL="minimal")
    def test_minimal_adds_nothing(self):
        request = _make_graphql_request({"query": "query getSites { sites { id } }"})
        log_kwargs = {}
        add_graphql_request_info(request=request, logger=None, log_kwargs=log_kwargs, sender=None)
        assert log_kwargs == {}

    @override_settings(ENV="production", GRAPHQL_LOG_LEVEL="names")
    def test_non_dev_env_adds_nothing(self):
        request = _make_graphql_request({"query": "query getSites { sites { id } }"})
        log_kwargs = {}
        add_graphql_request_info(request=request, logger=None, log_kwargs=log_kwargs, sender=None)
        assert log_kwargs == {}

    @override_settings(ENV="development", GRAPHQL_LOG_LEVEL="names")
    def test_non_graphql_request_ignored(self):
        factory = RequestFactory()
        request = factory.post("/api/other/", data="{}", content_type="application/json")
        log_kwargs = {}
        add_graphql_request_info(request=request, logger=None, log_kwargs=log_kwargs, sender=None)
        assert log_kwargs == {}

    @override_settings(ENV="development", GRAPHQL_LOG_LEVEL="full")
    def test_full_no_variables(self):
        request = _make_graphql_request({"query": "query getSites { sites { id } }"})
        log_kwargs = {}
        add_graphql_request_info(request=request, logger=None, log_kwargs=log_kwargs, sender=None)
        assert "graphql_variables" not in log_kwargs

    @override_settings(ENV="development", GRAPHQL_LOG_LEVEL="names")
    def test_malformed_json_does_not_crash(self):
        factory = RequestFactory()
        request = factory.post("/graphql/", data="not json", content_type="application/json")
        log_kwargs = {}
        add_graphql_request_info(request=request, logger=None, log_kwargs=log_kwargs, sender=None)
        assert log_kwargs == {}

    @override_settings(ENV="development", GRAPHQL_LOG_LEVEL="names")
    def test_get_request_ignored(self):
        factory = RequestFactory()
        request = factory.get("/graphql/")
        log_kwargs = {}
        add_graphql_request_info(request=request, logger=None, log_kwargs=log_kwargs, sender=None)
        assert log_kwargs == {}


@pytest.mark.unit
class TestAddGraphqlResponseInfo:
    @override_settings(ENV="development", GRAPHQL_LOG_LEVEL="names")
    def test_names_adds_operation(self):
        request = _make_graphql_request({"query": "query getSites { sites { id } }"})

        class FakeResponse:
            content = b'{"data": {}}'

        log_kwargs = {}
        add_graphql_response_info(
            request=request,
            logger=None,
            response=FakeResponse(),
            log_kwargs=log_kwargs,
            sender=None,
        )
        assert log_kwargs["graphql_operation"] == "getSites (query)"
        assert "graphql_response" not in log_kwargs

    @override_settings(ENV="development", GRAPHQL_LOG_LEVEL="full")
    def test_full_adds_response(self):
        request = _make_graphql_request({"query": "query getSites { sites { id } }"})

        class FakeResponse:
            content = b'{"data": {"sites": []}}'

        log_kwargs = {}
        add_graphql_response_info(
            request=request,
            logger=None,
            response=FakeResponse(),
            log_kwargs=log_kwargs,
            sender=None,
        )
        assert log_kwargs["graphql_operation"] == "getSites (query)"
        assert log_kwargs["graphql_response"] == {"data": {"sites": []}}

    @override_settings(ENV="development", GRAPHQL_LOG_LEVEL="names")
    def test_names_flags_graphql_errors(self):
        request = _make_graphql_request({"query": "query getSites { sites { id } }"})

        class FakeResponse:
            content = b'{"errors": [{"message": "Not found"}]}'

        log_kwargs = {}
        add_graphql_response_info(
            request=request,
            logger=None,
            response=FakeResponse(),
            log_kwargs=log_kwargs,
            sender=None,
        )
        assert log_kwargs["graphql_has_errors"] is True

    @override_settings(ENV="development", GRAPHQL_LOG_LEVEL="names")
    def test_names_no_error_flag_on_success(self):
        request = _make_graphql_request({"query": "query getSites { sites { id } }"})

        class FakeResponse:
            content = b'{"data": {"sites": []}}'

        log_kwargs = {}
        add_graphql_response_info(
            request=request,
            logger=None,
            response=FakeResponse(),
            log_kwargs=log_kwargs,
            sender=None,
        )
        assert "graphql_has_errors" not in log_kwargs

    @override_settings(ENV="development", GRAPHQL_LOG_LEVEL="names")
    def test_partial_errors_flagged(self):
        """GraphQL can return both data and errors (partial success)."""
        request = _make_graphql_request({"query": "query getSites { sites { id } }"})

        class FakeResponse:
            content = b'{"data": {"sites": []}, "errors": [{"message": "Partial failure"}]}'

        log_kwargs = {}
        add_graphql_response_info(
            request=request,
            logger=None,
            response=FakeResponse(),
            log_kwargs=log_kwargs,
            sender=None,
        )
        assert log_kwargs["graphql_has_errors"] is True


@pytest.mark.unit
class TestAddGraphqlErrorInfo:
    @override_settings(ENV="development", GRAPHQL_LOG_LEVEL="names")
    def test_names_adds_operation_on_exception(self):
        request = _make_graphql_request({"query": "mutation updateSite { update { id } }"})
        log_kwargs = {}
        add_graphql_error_info(
            request=request,
            logger=None,
            exception=Exception("boom"),
            log_kwargs=log_kwargs,
            sender=None,
        )
        assert log_kwargs["graphql_operation"] == "updateSite (mutation)"

    @override_settings(ENV="development", GRAPHQL_LOG_LEVEL="full")
    def test_full_adds_variables_on_exception(self):
        request = _make_graphql_request(
            {
                "query": "mutation updateSite($id: ID!) { updateSite(id: $id) { id } }",
                "variables": {"id": "123"},
            }
        )
        log_kwargs = {}
        add_graphql_error_info(
            request=request,
            logger=None,
            exception=Exception("boom"),
            log_kwargs=log_kwargs,
            sender=None,
        )
        assert log_kwargs["graphql_operation"] == "updateSite (mutation)"
        assert log_kwargs["graphql_variables"] == {"id": "123"}
