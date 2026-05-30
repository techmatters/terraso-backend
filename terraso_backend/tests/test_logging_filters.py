# Copyright © 2026 Technology Matters
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

import logging

import pytest
from config.logging_filters import SensitiveQueryParamFilter


def _record(msg):
    return logging.LogRecord(
        name="django_structlog.middlewares.request",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg=msg,
        args=None,
        exc_info=None,
    )


@pytest.mark.unit
class TestSensitiveQueryParamFilter:
    def setup_method(self):
        self.filt = SensitiveQueryParamFilter()

    def test_non_dict_message_passes_through(self):
        record = _record("plain text log line with code=secret123")
        assert self.filt.filter(record) is True
        assert record.msg == "plain text log line with code=secret123"

    def test_dict_without_request_passes_through(self):
        record = _record({"event": "something_happened", "user_id": "abc"})
        assert self.filt.filter(record) is True
        assert record.msg == {"event": "something_happened", "user_id": "abc"}

    def test_request_without_query_string_passes_through(self):
        record = _record({"request": "GET /healthz"})
        assert self.filt.filter(record) is True
        assert record.msg["request"] == "GET /healthz"

    def test_request_with_only_non_sensitive_params_unchanged(self):
        record = _record({"request": "GET /foo?bar=baz&qux=quux"})
        assert self.filt.filter(record) is True
        assert record.msg["request"] == "GET /foo?bar=baz&qux=quux"

    def test_oauth_code_redacted(self):
        record = _record(
            {
                "request": (
                    "GET /auth/google/callback?state=eyJabc"
                    "&iss=https%3A%2F%2Faccounts.google.com"
                    "&code=4%2F0AeoWuM-BnJBZm5yvDTgINVtknPeIJkuhT77S6e"
                    "&scope=email"
                )
            }
        )
        self.filt.filter(record)
        request = record.msg["request"]
        assert "code=[REDACTED]" in request
        assert "4%2F0AeoWuM" not in request
        # Non-sensitive params preserved
        assert "state=eyJabc" in request
        assert "iss=https%3A%2F%2Faccounts.google.com" in request
        assert "scope=email" in request

    def test_id_token_redacted(self):
        record = _record({"request": "GET /auth/apple/callback?id_token=eyJraw&state=foo"})
        self.filt.filter(record)
        assert record.msg["request"] == "GET /auth/apple/callback?id_token=[REDACTED]&state=foo"

    def test_access_token_redacted(self):
        record = _record({"request": "GET /x?access_token=abc&foo=bar"})
        self.filt.filter(record)
        assert record.msg["request"] == "GET /x?access_token=[REDACTED]&foo=bar"

    def test_refresh_token_redacted(self):
        record = _record({"request": "GET /x?refresh_token=abc&foo=bar"})
        self.filt.filter(record)
        assert record.msg["request"] == "GET /x?refresh_token=[REDACTED]&foo=bar"

    def test_arbitrary_underscore_token_redacted(self):
        record = _record({"request": "GET /x?session_token=abc&foo=bar"})
        self.filt.filter(record)
        assert record.msg["request"] == "GET /x?session_token=[REDACTED]&foo=bar"

    def test_multiple_sensitive_params_all_redacted(self):
        record = _record({"request": "GET /x?code=AAA&access_token=BBB&id_token=CCC&legit=keepme"})
        self.filt.filter(record)
        request = record.msg["request"]
        assert request == (
            "GET /x?code=[REDACTED]&access_token=[REDACTED]&id_token=[REDACTED]&legit=keepme"
        )

    def test_code_as_first_param_redacted(self):
        record = _record({"request": "GET /x?code=AAA&state=BBB"})
        self.filt.filter(record)
        assert record.msg["request"] == "GET /x?code=[REDACTED]&state=BBB"

    def test_code_as_last_param_redacted(self):
        record = _record({"request": "GET /x?state=BBB&code=AAA"})
        self.filt.filter(record)
        assert record.msg["request"] == "GET /x?state=BBB&code=[REDACTED]"

    def test_substring_keys_not_redacted(self):
        # 'decode' and 'barcode' end in 'code' but are not the 'code' param.
        record = _record({"request": "GET /x?decode=yes&barcode=12345"})
        self.filt.filter(record)
        assert record.msg["request"] == "GET /x?decode=yes&barcode=12345"

    def test_token_prefix_keys_not_redacted(self):
        # 'token_thing' does not end in '_token', so it's not in our sensitive set.
        record = _record({"request": "GET /x?token_thing=yes&foo=bar"})
        self.filt.filter(record)
        assert record.msg["request"] == "GET /x?token_thing=yes&foo=bar"

    def test_case_insensitive(self):
        record = _record({"request": "GET /x?CODE=AAA&ID_TOKEN=BBB"})
        self.filt.filter(record)
        assert record.msg["request"] == "GET /x?CODE=[REDACTED]&ID_TOKEN=[REDACTED]"

    def test_empty_sensitive_value_redacted(self):
        # Even an empty value is a leak attempt — keep the redaction marker.
        record = _record({"request": "GET /x?code=&state=foo"})
        self.filt.filter(record)
        assert record.msg["request"] == "GET /x?code=[REDACTED]&state=foo"

    def test_filter_returns_true_always(self):
        # This filter never drops records, only mutates them.
        assert self.filt.filter(_record("plain")) is True
        assert self.filt.filter(_record({"event": "x"})) is True
        assert self.filt.filter(_record({"request": "GET /x?code=AAA"})) is True
