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
        assert result[0].client_timestamp == time
        assert result[0].user_human_readable == user.full_name()
        assert result[0].resource_human_readable == resource.id
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
