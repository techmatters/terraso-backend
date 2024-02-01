# Copyright © 2023 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.

from datetime import datetime
from typing import Dict, Literal, Protocol

from apps.core.models import User

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
        user: User,
        action: ACTIONS,
        resource: object,
        metadata: KeyValue,
        client_time: datetime,
    ) -> None:
        ...
