
from datetime import datetime
from typing import List

from django.db import transaction

from . import AuditLog, AuditLogQuerier, KeyValue, models


class AuditLogService(AuditLog):
    """
    AuditLogService implements the AuditLog protocol
    """

    def log(self, values: List[KeyValue]) -> None:
        """
        log logs using key-value pairs
        """
        with transaction.atomic():
            log = models.Log()
            log.save()
            for key, value in values:
                if key == "client_time":
                    log.client_timestamp = datetime.fromtimestamp(value)
                    log.save()
                    continue
                key_value = models.KeyValue()
                key_value.key = key
                key_value.value = str(value)
                key_value.log = log
                key_value.save()

    def log_user_action(
            self,
            user: str,
            action: str,
            resource: str,
            client_time: datetime.timestamp
    ) -> None:
        """
        log_user_action logs a user action
        """
        self.log([
            ('user', user),
            ('action', action),
            ('resource', resource),
            ('client_time', client_time)
        ])


class AuditLogQuerierService(AuditLogQuerier):
    def get_logs(
            self,
            start: datetime.timestamp = datetime.min.timestamp(),
            end: datetime.timestamp = datetime.max.timestamp(),
    ) -> List[models.Log]:
        """
        get_logs gets all logs between start and end
        """
        return models.Log.objects.filter(client_timestamp__range=(start, end))

    def get_log_by_key_value(
        self,
        values: List[KeyValue],
        start: datetime.timestamp = datetime.min.timestamp(),
        end: datetime.timestamp = datetime.max.timestamp()
    ) -> List[models.Log]:
        """
        get_log_by_key_value gets all logs between start and end
        """
        logs = models.Log.objects.filter(client_timestamp__range=(start, end))
        for key, value in values:
            logs = logs.filter(keyvalue__key=key, keyvalue__value=value)
        return logs

    def get_log_by_user(
            self,
            user: str,
            start: datetime.timestamp = datetime.min.timestamp(),
            end: datetime.timestamp = datetime.max.timestamp()
    ) -> List[models.Log]:
        """
        get_log_by_user gets all logs between start and end
        """
        return self.get_log_by_key_value([('user', user)], start, end)

    def get_log_by_action(
            self,
            action: str,
            start: datetime.timestamp = datetime.min.timestamp(),
            end: datetime.timestamp = datetime.max.timestamp()
    ) -> List[models.Log]:
        """
        get_log_by_action gets all logs between start and end
        """
        return self.get_log_by_key_value([('action', action)], start, end)

    def get_log_by_resource(
            self,
            resource: str,
            start: datetime.timestamp = datetime.min.timestamp(),
            end: datetime.timestamp = datetime.max.timestamp()
    ) -> List[models.Log]:
        """
        get_log_by_resource gets all logs between start and end
        """
        return self.get_log_by_key_value([('resource', resource)], start, end)
