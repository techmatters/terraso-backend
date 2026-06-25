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

from datetime import timedelta

import pytest
from django.contrib import admin
from django.contrib.messages import constants as message_constants
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory

from apps.auth.services import JWTService
from apps.core.admin import UserAdmin, UserAdminCreationForm, create_partner_refresh_token
from apps.core.models import User

pytestmark = pytest.mark.django_db


def _request_with_messages():
    request = RequestFactory().post("/admin/core/user/")
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    request._messages = FallbackStorage(request)
    return request


def test_user_admin_add_view_form_builds_without_username():
    # Regression: GET /admin/core/user/add/ raised
    # FieldError(Unknown field(s) (username)) because DjangoUserAdmin's default
    # add_fieldsets assumes a `username` field this email-based model lacks.
    request = RequestFactory().get("/admin/core/user/add/")
    form_class = UserAdmin(User, admin.site).get_form(request, obj=None, change=False)
    assert "username" not in form_class.base_fields
    assert "email" in form_class.base_fields


def test_user_admin_creation_form_creates_email_user():
    form = UserAdminCreationForm(
        data={
            "email": "partner-bot@example.com",
            "password1": "Zx9-quoll-thicket-amber",
            "password2": "Zx9-quoll-thicket-amber",
        }
    )
    assert form.is_valid(), form.errors
    created = form.save()
    assert created.email == "partner-bot@example.com"
    assert User.objects.filter(pk=created.pk).exists()


def test_create_partner_refresh_token_is_a_valid_refresh_token(user):
    token = create_partner_refresh_token(user, timedelta(days=365 * 10))
    decoded = JWTService().verify_refresh_token(token)
    assert decoded["sub"] == str(user.id)
    assert decoded["refresh"] is True


def test_create_partner_refresh_token_ttl_is_honored(user):
    ten_year = JWTService().verify_refresh_token(
        create_partner_refresh_token(user, timedelta(days=365 * 10))
    )
    one_year = JWTService().verify_refresh_token(
        create_partner_refresh_token(user, timedelta(days=365))
    )
    # The TTL argument actually drives expiry: 10y token outlives the 1y token.
    assert ten_year["exp"] > one_year["exp"]


def test_mint_action_emits_token_for_a_single_user(user):
    request = _request_with_messages()
    UserAdmin(User, admin.site).mint_partner_refresh_token_10y(
        request, User.objects.filter(pk=user.pk)
    )
    msgs = list(get_messages(request))
    assert len(msgs) == 1
    assert msgs[0].level == message_constants.WARNING
    assert "Refresh token" in str(msgs[0].message)
    assert "10 years" in str(msgs[0].message)


def test_mint_action_requires_exactly_one_user(users):
    request = _request_with_messages()
    UserAdmin(User, admin.site).mint_partner_refresh_token_10y(request, User.objects.all())
    msgs = list(get_messages(request))
    assert len(msgs) == 1
    assert msgs[0].level == message_constants.ERROR
    assert "exactly one user" in str(msgs[0].message)
