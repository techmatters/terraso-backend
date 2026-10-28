# Copyright © 2021-2023 Technology Matters
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
from django.apps import AppConfig


class SoilIdConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.soil_id"

    def ready(self):
        import pandas as pd

        # The pinned soil-id algorithm (2026-09-30.0) predates pandas 3. It
        # calls Series.astype(str) and assumes the result contains Python
        # strings, but pandas 3's default str dtype preserves missing values as
        # NaN, which reach soil_id.utils.trim_fraction() as floats and raise
        # AttributeError. Restore pandas 2's object-based string inference so
        # the algorithm keeps receiving "nan"/"None" strings as before. This is
        # a compatibility setting for the third-party algorithm, not a pin.
        pd.set_option("future.infer_string", False)
