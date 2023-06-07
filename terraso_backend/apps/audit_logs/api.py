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

