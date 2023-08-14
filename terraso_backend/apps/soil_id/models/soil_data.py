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

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models.commons import BaseModel
from apps.project_management.models.sites import Site

CONCAVE = "concave"
CONVEX = "convex"
LINEAR = "linear"

SLOPE_SHAPES = ((CONCAVE, _("Concave")), (CONVEX, _("Convex")), (LINEAR, _("Linear")))

HILLS_MOUNTAINS = "Hills/Mountains"
SUMMIT = "Summit"
SHOULDER = "Shoulder"
BACKSLOPE = "Backslope"
ALLUVIAL_FAN = "Alluvial Fan"
FLOODPLAIN_BASIN = "Floodpain/Basin"
TERRACE = "Terrace"
TREAD = "Tread"
RISER = "Riser"
FLAT_LOW_ROLLING_PLAIN = "Flat/Low Rolling Plain"
PLAYA = "Playa"
DUNES = "Dunes"

LANDSCAPE_POSITIONS = (
    (
        HILLS_MOUNTAINS,
        _((SUMMIT, _("Summit")), (SHOULDER, _("Shoulder")), (BACKSLOPE, _("Backslope"))),
    ),
    (ALLUVIAL_FAN, _("Alluvial Fan")),
    (FLOODPLAIN_BASIN, _("Floodpain/Basin")),
    (TERRACE, _((TREAD, _("Tread")), (RISER, _("Riser")))),
    (FLAT_LOW_ROLLING_PLAIN, _("Flat/Low Rolling Plain")),
    (PLAYA, _("Playa")),
    (DUNES, _("Dunes")),
)

FLAT = "0 - 2% (flat)"
GENTLE = "2 - 5% (gentle)"
MODERATE = "5 - 10% (moderate)"
ROLLING = "10 - 15% (rolling)"
HILLY = "15 - 30% (hilly)"
STEEP = "30 - 50% (steep)"
MODERATELY_STEEP = "50 - 60% (moderately steep)"
VERY_STEEP = "60 - 100% (very steep)"
STEEPEST = "> 100% (steepest)"

SLOPE_RANGES = ((FLAT, _("0 - 2% (flat)")),
                (GENTLE, _("2 - 5% (gentle)")),
                (MODERATE, _("5 - 10% (moderate)")),
                (ROLLING, _("10 - 15% (rolling)")),
                (HILLY, _("15 - 30% (hilly)")),
                (STEEP, _("30 - 50% (steep)")),
                (MODERATELY_STEEP, _("50 - 60% (moderately steep)")),
                (VERY_STEEP, _("60 - 100% (very steep)")),
                (STEEPEST, _("> 100% (steepest)")))

class SoilData(BaseModel):
    site = models.OneToOneField(Site, on_delete=models.CASCADE)
    down_slope = models.IntegerField(
        null=True, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    cross_slope = models.IntegerField(
        null=True, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    slope_shape = models.CharField(null=True, choices=SLOPE_SHAPES)
    slope_landscape_position = models.CharField(null=True, choices=LANDSCAPE_POSITIONS)
    slope_aspect = models.IntegerField(null=True, validators=[MinValueValidator(0), MaxValueValidator(359)])
    slope_range_select = models.CharField(null=True, choices=SLOPE_RANGES)
    slope_range_manual = models.IntegerField(null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    slope_steepness_percent = models.IntegerField(null=True, validators=[MinValueValidator(0)])
    slope_steepness_degree = models.IntegerField(null=True, validators=[MinValueValidator(0), MaxValueValidator(90)])