
from typing import Optional, Protocol

from . import models


class SoilIdAPI(Protocol):
    # SoildIdService is a protocol that defines the interface for any external module
    # that wants intearct with the soil ID. The protocol is defined in the

    def get_soil_id(self, soil_id: str) -> Optional[models.Site]:
        ...
