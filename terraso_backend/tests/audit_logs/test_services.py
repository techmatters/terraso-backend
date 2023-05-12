import datetime

from django.test import TestCase
from django.contrib.contenttypes.models import ContentType

from apps.core.models import User
from apps.audit_logs import services, models, api
# Create your tests here.


class AuditLogServiceTest(TestCase):
    def test_create_log(self):
        log = services.AuditLogService()
        user = User(email="a@a.com")
        user.save()
        resource = User(email="b@b.com")
        resource.save()

        action = 1
        metadata = []
        time = datetime.datetime.now()
        metadata = [api.KeyValue(("client_time", time))]
        log.log(user, action, resource, metadata)

        result = models.Log.objects.all()
        assert len(result) == 1

    def test_create_log_invalid_user(self):
        log = services.AuditLogService()
        user = object()
        resource = User(email="b@b.com")
        resource.save()
        action = 1
        time = datetime.datetime.now()
        metadata = [api.KeyValue(("client_time", time))]
        with self.assertRaises(ValueError):
            log.log(user, action, resource, metadata)

    def test_create_log_invalid_action(self):
        log = services.AuditLogService()
        user = User(email="a@a.com")
        user.save()
        resource = User(email="b@b.com")
        resource.save()
        action = -1
        time = datetime.datetime.now()
        metadata = [api.KeyValue(("client_time", time))]
        with self.assertRaises(ValueError):
            log.log(user, action, resource, metadata)

    def test_create_log_invalid_resource(self):
        log = services.AuditLogService()
        user = User(email="a@a.com")
        user.save()
        resource = object()
        action = 1
        metadata = [("client_time", 1234567890)]
        with self.assertRaises(ValueError):
            log.log(user, action, resource, metadata)


class AuditLogModelTest(TestCase):
    def test_get_string(self):
        user = User(email="a@a.com")
        user.save()
        resource = User(email="b@b.com")
        resource.save()

        action = 1
        log = models.Log(user=user, event=action, resource_id=resource.id)
        result = log.get_string()
        assert result == str(log)

    def test_get_string_with_template(self):
        user = User(email="a@a.com")
        user.save()
        resource = User(email="b@b.com")
        resource.save()
        action = 1
        content_type = ContentType.objects.get_for_model(resource)
        metadata_dict = {
            "user": user.email,
            "resource": resource.email,
            "action": action
        }
        log = models.Log(
            user=user,
            event=action,
            resource_id=str(resource.id),
            content_type=content_type,
            metadata=metadata_dict
        )
        result = log.get_string("User {user} {action} {resource}")
        assert result == "User a@a.com 1 b@b.com"
