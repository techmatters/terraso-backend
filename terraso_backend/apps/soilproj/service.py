
from typing import Optional

from . import models


class SoilService():

    def get_site_by_name(self, name: str) -> Optional[models.Site]:
        # get_site_by_name returns a site and queries it by name.
        # It returns None if no site is found
        return models.Site.objects.filter(name=name).first()
