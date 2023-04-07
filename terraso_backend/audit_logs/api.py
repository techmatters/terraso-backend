from datetime import datetime
from typing import List, NewType, Protocol, Tuple

from . import models

# KeyValue represents a key-value pair
KeyValue = NewType('KeyValue', Tuple[str, any])


class AuditLog(Protocol):
    """
    AuditLogProtocol is a protocol that defines the interface for the audit log
    """

    def log(self, values: List[KeyValue]) -> None:
        ...

    def log_user_action(
            self,
            user: str,
            action: str,
            resource: str,
            client_time: datetime.timestamp
    ) -> None:
        ...


class AuditLogQuerier(Protocol):
    """
    AuditLogQuerierProtocol is a protocol that defines the interface for the
    audit log querier
    """

    def get_logs(
            self,
            start: datetime.timestamp,
            end: datetime.timestamp
    ) -> List[models.Log]:
        ...

    def get_log_by_key_value(
        self,
        values: List[KeyValue],
        start: datetime.timestamp,
        end: datetime.timestamp
    ) -> List[models.Log]:
        ...

    def get_log_by_user(
            self,
            user: str,
            start: datetime.timestamp,
            end: datetime.timestamp
    ) -> List[models.Log]:
        ...

    def get_log_by_action(
            self,
            action: str,
            start: datetime.timestamp,
            end: datetime.timestamp
    ) -> List[models.Log]:
        ...

    def get_log_by_resource(self, resource: str) -> List[models.Log]:
        ...
