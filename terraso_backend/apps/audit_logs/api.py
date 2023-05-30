from datetime import datetime
from typing import List, NewType, Protocol, Tuple

from . import models

# KeyValue represents a key-value pair
KeyValue = NewType('KeyValue', Tuple[str, object | str])

CREATE = models.CREATE
READ = models.READ
CHANGE = models.CHANGE
DELETE = models.DELETE


class AuditLog(Protocol):
    """
    AuditLogProtocol is a protocol that defines the interface for the audit log
    """

    def log(self, user: object, action: int, resource: object, metadata: List[KeyValue]) -> None:
        ...



class AuditLogQuerier(Protocol):
    """
    AuditLogQuerierProtocol is a protocol that defines the interface for the
    audit log querier
    """

    def get_logs(
            self,
            start: datetime,
            end: datetime
    ) -> List[models.Log]:
        ...

    def get_log_by_id(self, log_id: str) -> models.Log:
        ...

    def get_log_by_key_value(
        self,
        values: List[KeyValue],
        start: datetime,
        end: datetime
    ) -> List[models.Log]:
        ...

    def get_log_by_user(
            self,
            user: str,
            start: datetime,
            end: datetime
    ) -> List[models.Log]:
        ...

    def get_log_by_action(
            self,
            action: str,
            start: datetime,
            end: datetime
    ) -> List[models.Log]:
        ...

    def get_log_by_resource(self, resource: str) -> List[models.Log]:
        ...

    def log_to_str(self, logs: models.Log, template: str) -> str:
        ...

    def logs_to_str(self, logs: List[models.Log], template: str) -> List[str]:
        ...


