# Copyright © 2024 Technology Matters
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

from django.db import models

from apps.core.models import User
from apps.core.models.commons import BaseModel
from apps.project_management.models.sites import Site


# NOTE: this table may contain data associated with sites that was submitted
#       by unauthorized (but still authenticated) users. such requests may have
#       an update_failure_reason of null or "NOT_ALLOWED". unless a user is
#       handcrafting malicious requests, this will be because a user had
#       authorization to enter data for a site, then went offline and made
#       changes simultaneous to losing authorization to enter data for that site
class SoilDataHistory(BaseModel):
    site = models.ForeignKey(Site, null=True, on_delete=models.CASCADE)
    changed_by = models.ForeignKey(User, on_delete=models.CASCADE)
    update_succeeded = models.BooleanField(null=False, blank=False, default=False)
    update_failure_reason = models.TextField(null=True)

    # intended JSON schema: {
    #   ...soilDataInputs,
    #   "depth_dependent_data": [{
    #     "depth_interval": {
    #       "start": number,
    #       "end": number
    #     },
    #     ...depthDependentInputs
    #   }],
    #   "depth_intervals": [{
    #     "depth_interval": {
    #       "start": number,
    #       "end": number
    #     },
    #     ...depthIntervalConfig
    #   }],
    #   "deleted_depth_intervals": [{
    #     "depth_interval": {
    #       "start": number,
    #       "end": number
    #     }
    #   }]
    # }
    soil_data_changes = models.JSONField()
