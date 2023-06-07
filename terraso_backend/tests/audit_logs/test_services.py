import datetime

from django.contrib.contenttypes.models import ContentType
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
        metadata = {'client_time': time}
        log.log(user, action, resource, metadata)

        result = models.Log.objects.all()
        assert len(result) == 1

    def test_create_log_invalid_user(self):
        log = services.new_audit_logger()
        user = object()
        resource = User(email="b@b.com")
        resource.save()
        action = api.CREATE
        time = datetime.datetime.now()
        metadata = {'client_time': time}
        with self.assertRaises(ValueError):
            log.log(user, action, resource, metadata)

    def test_create_log_invalid_action(self):
        log = services.new_audit_logger()
        user = User(email="a@a.com")
        user.save()
        resource = User(email="b@b.com")
        resource.save()
        action = "INVALID"
        time = datetime.datetime.now()
        metadata = {'client_time': time}
        with self.assertRaises(ValueError):
            log.log(user, action, resource, metadata)

    def test_create_log_invalid_resource(self):
        log = services.new_audit_logger()
        user = User(email="a@a.com")
        user.save()
        resource = object()
        action = api.CREATE
        metadata = {'client_time': 1234567890}
        with self.assertRaises(ValueError):
            log.log(user, action, resource, metadata)
