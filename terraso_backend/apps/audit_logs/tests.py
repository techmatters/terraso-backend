from django.test import TestCase

from core.models import User
from . import services, models, api

# Create your tests here.


class MockUser:
    def __init__(self, id):
        self.id = id

    def human_readable(self):
        return "MockUser {}".format(self.id)


class MockResource:
    def __init__(self, id):
        self.id = id
        self.__str__ = lambda: "MockResource"

    def human_readable(self):
        return "MockResource {}".format(self.id)


class AuditLogServiceTest(TestCase):
    def test_create_log(self):
        log = services.AuditLogService()
        user = User()
        resource = MockResource(1)
        action = "CREATE"
        metadata = [api.KeyValue(("client_time", 1234567890))]
        log.log(user, action, resource, metadata)

        result = models.Log.objects.all()
        assert len(result) == 1

    def test_create_log_invalid_user(self):
        log = services.AuditLogService()
        user = object()
        resource = MockResource(1)
        action = "CREATE"
        metadata = [("client_time", 1234567890)]
        with self.assertRaises(ValueError):
            log.log(user, action, resource, metadata)

    def test_create_log_invalid_action(self):
        log = services.AuditLogService()
        user = MockUser(1)
        resource = MockResource(1)
        action = "INVALID"
        metadata = [("client_time", 1234567890)]
        with self.assertRaises(ValueError):
            log.log(user, action, resource, metadata)

    def test_create_log_invalid_resource(self):
        log = services.AuditLogService()
        user = MockUser(1)
        resource = object()
        action = "CREATE"
        metadata = [("client_time", 1234567890)]
        with self.assertRaises(ValueError):
            log.log(user, action, resource, metadata)


class AuditLogModelTest(TestCase):
    def test_get_string(self):
        user = MockUser(1)
        resource = MockResource(1)
        action = "CREATE"
        metadata = [("client_time", 1234567890)]
        log = models.Log(
            user=user,
            action=action,
            resource_id=resource.id,
            content_type=resource.__class__.__name__,
            resource_repr=resource.__repr__(),
            metadata=metadata
        )
        log.save()
        result = log.get_string()
        assert result == "MockUser 1 CREATE MockResource 1"

    def test_get_string_with_template(self):
        user = MockUser(1)
        resource = MockResource(1)
        action = "CREATE"
        metadata = [("client_time", 1234567890)]
        log = models.Log(
            user=user,
            action=action,
            resource_id=resource.id,
            content_type=resource.__class__.__name__,
            resource_repr=resource.__repr__(),
            metadata=metadata
        )
        log.save()
        result = log.get_string("User {user} {action} {resource}")
        assert result == "User MockUser 1 CREATE MockResource 1"
