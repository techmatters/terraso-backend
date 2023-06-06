import typing
from datetime import datetime
from typing import List, Optional

from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models.query import QuerySet

from . import api, models

TEMPLATE = "{client_time} - {user} {action} {resource}"


class _AuditLogService:
    """
    AuditLogService implements the AuditLog protocol
    """

    def log(
        self,
        user: object,
        action: int,
        resource: object,
        metadata: typing.Optional[List[api.KeyValue]] = None,
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

        if not hasattr(models.Events, action):
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
        resource_obj = resource

        resource_repr = resource.__dict__.__str__()

        if metadata is None:
            metadata = []

        with transaction.atomic():
            log = models.Log(
                user=user,
                event=action,
                resource_id=resource_id,
                resource_content_type=content_type,
                resource_object=resource_obj,
                resource_json_repr=resource_repr,
            )
            metadata_dict = {
                "user": str(user_readable),
                "resource": str(resource_human_readable),
                "action": action,
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


def new_audit_logger() -> api.AuditLog:
    """
    new_audit_logger creates a new audit log
    """
    return _AuditLogService()
