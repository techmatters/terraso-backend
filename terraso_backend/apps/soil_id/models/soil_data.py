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

from apps.core.models.commons import BaseModel
from apps.project_management.models.sites import Site


class SoilData(BaseModel):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name="soil_data")

    class SlopeShape(models.TextChoices):
        CONCAVE = "CONCAVE"
        CONVEX = "CONVEX"
        LINEAR = "LINEAR"

    down_slope = models.CharField(blank=True, choices=SlopeShape.choices)
    cross_slope = models.CharField(blank=True, choices=SlopeShape.choices)

    bedrock = models.PositiveIntegerField(blank=True, null=True)

    class LandscapePosition(models.TextChoices):
        HILLS_MOUNTAINS = "HILLS_MOUNTAINS", "Hills/Mountains"
        HILLS_MOUNTAINS_SUMMIT = "HILLS_MOUNTAINS_SUMMIT", "Hills/Mountains (Summit)"
        HILLS_MOUNTAINS_SHOULDER = "HILLS_MOUNTAINS_SHOULDER", "Hills/Mountains (Shoulder)"
        HILLS_MOUNTAINS_BACKSLOPE = "HILLS_MOUNTAINS_BACKSLOPE", "Hills/Mountains (Backslope)"
        ALLUVIAL_FAN = "ALLUVIAL_FAN"
        FLOODPLAIN_BASIN = "FLOODPLAIN_BASIN", "Floodplain/Basin"
        TERRACE = "TERRACE"
        TERRACE_TREAD = "TERRACE_TREAD", "Terrace (Tread)"
        TERRACE_RISER = "TERRACE_RISER", "Terrace (Riser)"
        FLAT_LOW_ROLLING_PLAIN = "FLAT_LOW_ROLLING_PLAIN", "Flat/Low Rolling Plain"
        PLAYA = "PLAYA"
        DUNES = "DUNES"

    slope_landscape_position = models.CharField(blank=True, choices=LandscapePosition.choices)

    slope_aspect = models.IntegerField(
        blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(359)]
    )

    class SlopeSteepness(models.TextChoices):
        FLAT = "FLAT", "0 - 2% (flat)"
        GENTLE = "GENTLE", "2 - 5% (gentle)"
        MODERATE = "MODERATE", "5 - 10% (moderate)"
        ROLLING = "ROLLING", "10 - 15% (rolling)"
        HILLY = "HILLY", "15 - 30% (hilly)"
        STEEP = "STEEP", "30 - 50% (steep)"
        MODERATELY_STEEP = "MODERATELY_STEEP", "50 - 60% (moderately steep)"
        VERY_STEEP = "VERY_STEEP", "60 - 100% (very steep)"
        STEEPEST = "STEEPEST", "100%+ (steepest)"

    slope_steepness_select = models.CharField(blank=True, choices=SlopeSteepness.choices)

    slope_steepness_percent = models.IntegerField(
        blank=True, null=True, validators=[MinValueValidator(0)]
    )

    slope_steepness_degree = models.IntegerField(
        blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(90)]
    )
