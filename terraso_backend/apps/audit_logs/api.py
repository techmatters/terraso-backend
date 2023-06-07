from datetime import datetime
from typing import Dict, List, Literal, Protocol

from . import models
from .models import Events

# KeyValue represents a key-value pair
KeyValue = Dict[str, object | str | int | datetime]

ACTIONS = Literal[Events.CREATE, Events.READ, Events.CHANGE, Events.DELETE]

CREATE = models.Events.CREATE
READ = models.Events.READ
CHANGE = models.Events.CHANGE
DELETE = models.Events.DELETE


class AuditLog(Protocol):
    """
    AuditLogProtocol is a protocol that defines the interface for the audit log
    """

    def log(
        self,
        user: object,
        action: ACTIONS,
        resource: object,
        metadata: KeyValue,
        client_time: datetime,
    ) -> None:
        ...


class AuditLogQuerier(Protocol):
    """
    AuditLogQuerierProtocol is a protocol that defines the interface for the
    audit log querier
    """

    def get_logs(self, start: datetime, end: datetime) -> List[models.Log]:
        ...

    def get_log_by_id(self, log_id: str) -> models.Log:
        ...

    def get_log_by_key_value(
        self, values: List[KeyValue], start: datetime, end: datetime
    ) -> List[models.Log]:
        ...

    def get_log_by_user(self, user: str, start: datetime, end: datetime) -> List[models.Log]:
        ...

    def get_log_by_action(self, action: str, start: datetime, end: datetime) -> List[models.Log]:
        ...

    def get_log_by_resource(self, resource: str) -> List[models.Log]:
        ...

    def log_to_str(self, logs: models.Log, template: str) -> str:
        ...

    def logs_to_str(self, logs: List[models.Log], template: str) -> List[str]:
        ...
