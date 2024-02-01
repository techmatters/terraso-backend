# Copyright © 2023 Technology Matters
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

import datetime

from django.test import TestCase

from apps.audit_logs import api, models, services
from apps.core.models import User


class AuditLogServiceTest(TestCase):
    def test_create_log(self):
        log = services.new_audit_logger()
        user = User(email="a@a.com")
        user.save()
        resource = User(email="b@b.com")
        resource.save()

        action = api.CREATE
        time = datetime.datetime.now()
        metadata = {"some_key": "some_value"}
        log.log(user, action, resource, metadata, time)

        result = models.Log.objects.all()
        assert len(result) == 1
        assert result[0].user.id == user.id
        assert result[0].event == action.CREATE.value
        assert result[0].resource_object == resource
        assert result[0].user_human_readable == user.full_name()
        assert result[0].resource_human_readable == str(resource.id)
        assert result[0].metadata["some_key"] == "some_value"

    def test_create_log_invalid_user(self):
        log = services.new_audit_logger()
        user = object()
        resource = User(email="b@b.com")
        resource.save()
        action = api.CREATE
        time = datetime.datetime.now()
        metadata = {"some_key": "some_value"}
        with self.assertRaises(ValueError):
            log.log(user, action, resource, metadata, time)

    def test_create_log_invalid_action(self):
        log = services.new_audit_logger()
        user = User(email="a@a.com")
        user.save()
        resource = User(email="b@b.com")
        resource.save()
        action = "INVALID"
        time = datetime.datetime.now()
        metadata = {"some_key": "some_value"}
        with self.assertRaises(ValueError):
            log.log(user, action, resource, metadata, time)

    def test_create_log_invalid_resource(self):
        log = services.new_audit_logger()
        user = User(email="a@a.com")
        user.save()
        resource = object()
        action = api.CREATE
        time = datetime.datetime.now()
        metadata = {"some_key": "some_value"}
        with self.assertRaises(ValueError):
            log.log(user, action, resource, metadata, time)
