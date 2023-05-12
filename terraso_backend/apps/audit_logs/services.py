from datetime import datetime
from typing import List, Optional

from django.contrib.contenttypes.models import ContentType

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models.query import QuerySet

from . import api, models

TEMPLATE = "{client_time} - {user} {action} {resource}"


class AuditLogService():
    """
    AuditLogService implements the AuditLog protocol
    """

    def log(
            self,
            user: object,
            action: int,
            resource: object,
            metadata: List[api.KeyValue]
    ) -> None:
        """
        log logs an action performed by a user on a resource
        example:
            log(user, "create", resource, [("client_time", 1234567890)])
            :param metadata:
            :param action:
            :param user:
            :type resource: object
        """
        if not hasattr(user, "id"):
            raise ValueError("Invalid user")

        get_user_readable = getattr(user, "human_readable", None)
        user_readable = get_user_readable() if callable(get_user_readable) else user.id

        valid_action = False
        for e in models.EVENT_CHOICES:
            if e[0] == action:
                valid_action = True
                break
        if valid_action is False:
            raise ValueError("Invalid action")

        resource_id = resource.id if hasattr(resource, "id") else None
        if resource_id is None:
            raise ValueError("Invalid resource")

        get_resource_human_readable = getattr(resource, "human_readable", None)
        if callable(get_resource_human_readable):
            resource_human_readable = get_resource_human_readable()
        else:
            resource_human_readable = resource_id

        content_type = ContentType.objects.get_for_model(resource)

        resource_repr = resource.__repr__()

        with transaction.atomic():
            log = models.Log(
                user=user,
                event=action,
                resource_id=resource_id,
                content_type=content_type,
                resource_json_repr=resource_repr
            )
            metadata_dict = {
                "user": str(user_readable),
                "resource": str(resource_human_readable),
                "action": action
            }

            for key, value in metadata:
                if key == "client_time":
                    log.client_timestamp = value
                    continue
                metadata_dict[key] = value

            if log.client_timestamp is None:
                log.client_timestamp = datetime.now()

            metadata_dict["client_time"] = str(log.client_timestamp)
            log.metadata = metadata_dict
            log.save()


class LogData:
    """
    LazyPaginator implements the Paginator protocol
    """

    def __init__(self, data: QuerySet):
        self.data = data

    def get_paginator(self, page_size: int = 10):
        return Paginator(self.data, page_size)

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)


class AuditLogQuerierService():
    """
    AuditLogQuerierService implements the AuditLogQuerier protocol
    """

    template: str

    def __init__(self, template: str = TEMPLATE):
        self.template = template

    def get_logs(
            self,
            start: datetime = datetime.min,
            end: datetime = datetime.max,
    ) -> LogData:
        logs = models.Log.objects.filter(client_timestamp__range=(start, end))
        return LogData(logs)

    def get_log_by_id(
            self,
            log_id: str,
    ) -> LogData:
        result = models.Log.objects.filter(id=log_id)
        return LogData(result)

    def get_log_by_key_value(
            self,
            values: List[api.KeyValue],
            start: datetime = datetime.min,
            end: datetime = datetime.max,
    ) -> LogData:
        """
        get_log_by_key_value gets all logs between start and end
        """
        logs = models.Log.objects.filter(client_timestamp__range=(start, end))
        for key, value in values:
            if key == "user_id":
                logs = logs.filter(user__id=value)
            elif key == "action":
                logs = logs.filter(action=value)
            elif key == "resource_id":
                logs = logs.filter(resource_id=value)
            elif key == "resource_type":
                logs = logs.filter(content_type=value)

            logs = logs.filter(metadata__contains={key: value})

        return LogData(logs)

    def get_log_by_user(
            self,
            user_id: str,
            start: datetime = datetime.min,
            end: datetime = datetime.max,
    ) -> LogData:
        """
        get_log_by_user gets all logs between start and end
        """
        return self.get_log_by_key_value([api.KeyValue(('user_id', user_id))], start, end)

    def get_log_by_action(
            self,
            action: str,
            start: datetime = datetime.min,
            end: datetime = datetime.max,
    ) -> LogData:
        """
        get_log_by_action gets all logs between start and end
        """
        return self.get_log_by_key_value([api.KeyValue(('action', action))], start, end)

    def get_log_by_resource(
            self,
            resource_id: str,
            start: datetime = datetime.min,
            end: datetime = datetime.max
    ) -> LogData:
        """
        get_log_by_resource gets all logs between start and end
        """
        return self.get_log_by_key_value([api.KeyValue(('resource', resource_id))], start, end)

    def log_to_str(self, log: models.Log, template: Optional[str] = None) -> str:
        """
        log_to_str converts a log to a string
        """
        if template is None:
            template = self.template
        return log.get_string(template)

    def logs_to_str(self, logs: List[models.Log], template: Optional[str] = None) -> List[str]:
        """
        logs_to_str converts a list of logs to a list of strings
        """
        return [self.log_to_str(log, template) for log in logs]
