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
from django.forms import ValidationError

from apps.core.models.commons import BaseModel
from apps.project_management.models.sites import Site
from apps.soil_id.models.depth_interval import BaseDepthInterval


def default_depth_intervals():
    return []


def validate_depth_intervals(intervals):
    if not isinstance(intervals, list):
        raise ValidationError(f"Depth intervals must be list, got {intervals}")
    for index, interval in enumerate(intervals):
        if not isinstance(interval, dict) or len(interval) != 2:
            raise ValidationError(f"Depth interval must be two element dict, got {interval}")
        for field in ["start", "end"]:
            if field not in interval or not isinstance(interval[field], int):
                raise ValidationError(
                    f"Depth interval {field} must exist and be integer, got {interval[field]}"
                )
        if interval["start"] < 0 or interval["end"] > 200:
            raise ValidationError(f"Depth interval must be between 0 and 200, got {interval}")
        if interval["start"] >= interval["end"]:
            raise ValidationError(f"Depth interval start must be less than end, got {interval}")
        if index + 1 < len(intervals) and interval["end"] > intervals[index + 1]["start"]:
            raise ValidationError(
                f"""
                Depth interval must end at or before next interval,
                got {interval} followed by {intervals[index + 1]}
                """
            )


class SoilData(BaseModel):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name="soil_data")

    class SlopeShape(models.TextChoices):
        CONCAVE = "CONCAVE"
        CONVEX = "CONVEX"
        LINEAR = "LINEAR"

    down_slope = models.CharField(blank=True, null=True, choices=SlopeShape.choices)
    cross_slope = models.CharField(blank=True, null=True, choices=SlopeShape.choices)

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

    slope_landscape_position = models.CharField(
        blank=True, null=True, choices=LandscapePosition.choices
    )

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

    slope_steepness_select = models.CharField(blank=True, null=True, choices=SlopeSteepness.choices)

    slope_steepness_percent = models.IntegerField(
        blank=True, null=True, validators=[MinValueValidator(0)]
    )

    slope_steepness_degree = models.IntegerField(
        blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(90)]
    )

    class SurfaceCracks(models.TextChoices):
        NO_CRACKING = "NO_CRACKING", "No cracking"
        SURFACE_CRACKING_ONLY = "SURFACE_CRACKING_ONLY", "Surface cracking only"
        DEEP_VERTICAL_CRACKS = "DEEP_VERTICAL_CRACKS", "Deep vertical cracks"

    surface_cracks_select = models.CharField(blank=True, null=True, choices=SurfaceCracks.choices)

    class SurfaceSalt(models.TextChoices):
        NO_SALT = "NO_SALT", "No salt"
        SMALL_TEMPORARY_PATCHES = "SMALL_TEMPORARY_PATCHES", "Small, temporary patches"
        MOST_OF_SURFACE = "MOST_OF_SURFACE", "Yes, most of surface"

    surface_salt_select = models.CharField(blank=True, null=True, choices=SurfaceSalt.choices)

    class Flooding(models.TextChoices):
        NONE = "NONE", "None"
        RARE = "RARE", "Rare to occasional"
        OCCASIONAL = "OCCASIONAL", "Occasional"
        FREQUENT = "FREQUENT", "Frequent"
        VERY_FREQUENT = "VERY_FREQUENT", "Very frequent"

    flooding_select = models.CharField(blank=True, null=True, choices=Flooding.choices)

    class LimeRequirements(models.TextChoices):
        LITTLE_OR_NO = "LITTLE_OR_NO", "Little or no lime required"
        SOME = "SOME", "Some amounts of lime required"
        HIGH = "HIGH", "High amounts of lime required"
        VERY_DIFFICULT = "VERY_DIFFICULT", "Very difficult to modify with lime"

    lime_requirements_select = models.CharField(
        blank=True, null=True, choices=LimeRequirements.choices
    )

    class SurfaceStoniness(models.TextChoices):
        LESS_THAN_01 = "LESS_THAN_01", "< 0.1%"
        BETWEEN_01_AND_3 = "BETWEEN_01_AND_3", "0.1 to 3%"
        BETWEEN_3_AND_15 = "BETWEEN_3_AND_15", "3 to 15%"
        BETWEEN_15_AND_50 = "BETWEEN_15_AND_50", "15 to 50%"
        BETWEEN_50_AND_90 = "BETWEEN_50_AND_90", "50 - 90%"
        GREATER_THAN_90 = "GREATER_THAN_90", "> 90%"

    surface_stoniness_select = models.CharField(
        blank=True, null=True, choices=SurfaceStoniness.choices
    )

    class WaterTableDepth(models.TextChoices):
        NOT_FOUND = "NOT_FOUND", "Not found"
        LESS_THAN_30_CM = "LESS_THAN_30_CM", "<30 cm"
        BETWEEN_30_AND_45_CM = "BETWEEN_30_AND_45_CM", "30 to 45 cm"
        BETWEEN_45_AND_75_CM = "BETWEEN_45_AND_75_CM", "45 to 75 cm"
        BETWEEN_75_AND_120_CM = "BETWEEN_75_AND_120_CM", "75 to 120 cm"
        GREATER_THAN_120_CM = "GREATER_THAN_120_CM", "> 120 cm"

    water_table_depth_select = models.CharField(
        blank=True, null=True, choices=WaterTableDepth.choices
    )

    class SoilDepth(models.TextChoices):
        NOT_FOUND = "NOT_FOUND", "Not found"
        TWENTY_CM_OR_LESS = "TWENTY_CM_OR_LESS", "20 cm or less"
        GREATER_THAN_20_LESS_THAN_50_CM = (
            "GREATER_THAN_20_LESS_THAN_50_CM",
            "Greater than 20 and less than 50 cm",
        )
        BETWEEN_50_AND_70_CM = "BETWEEN_50_AND_70_CM", "Between 50 and 70 cm"
        GREATER_THAN_70_LESS_THAN_100_CM = (
            "GREATER_THAN_70_LESS_THAN_100_CM",
            "Greater than 70 and less than 100 cm",
        )
        HUNDRED_CM_OR_GREATER = "HUNDRED_CM_OR_GREATER", "100 cm or greater"

    soil_depth_select = models.CharField(blank=True, null=True, choices=SoilDepth.choices)

    class LandCover(models.TextChoices):
        FOREST = "FOREST", "Forest"
        SHRUBLAND = "SHRUBLAND", "Shrubland"
        GRASSLAND = "GRASSLAND", "Grassland"
        SAVANNA = "SAVANNA", "Savanna"
        GARDEN = "GARDEN", "Garden"
        CROPLAND = "CROPLAND", "Cropland"
        VILLAGE_OR_CITY = "VILLAGE_OR_CITY", "Village or City"
        BARREN = "BARREN", "Barren, no vegetation or structures"
        WATER = "WATER", "Water"

    land_cover_select = models.CharField(blank=True, null=True, choices=LandCover.choices)

    class Grazing(models.TextChoices):
        NOT_GRAZED = "NOT_GRAZED", "Not Grazed"
        CATTLE = "CATTLE", "Cattle"
        HORSE = "HORSE", "Horse"
        GOAT = "GOAT", "Goat"
        SHEEP = "SHEEP", "Sheep"
        PIG = "PIG", "Pig"
        CAMEL = "CAMEL", "Camel"
        WILDLIFE_FOREST = "WILDLIFE_FOREST", "Wildlife (forest, deer)"
        WILDLIFE_GRASSLANDS = "WILDLIFE_GRASSLANDS", "Wildlife (grasslands, giraffes, ibex)"

    grazing_select = models.CharField(blank=True, null=True, choices=Grazing.choices)

    class SoilDataDepthIntervalPreset(models.TextChoices):
        LANDPKS = "LANDPKS"
        NRCS = "NRCS"
        CUSTOM = "CUSTOM"

    depth_interval_preset = models.CharField(
        choices=SoilDataDepthIntervalPreset.choices,
        default=SoilDataDepthIntervalPreset.LANDPKS.value,
    )


class SoilDataDepthInterval(BaseModel, BaseDepthInterval):
    soil_data = models.ForeignKey(
        SoilData, on_delete=models.CASCADE, related_name="depth_intervals"
    )
    label = models.CharField(blank=True, max_length=10)

    class Meta(BaseModel.Meta):
        ordering = ["depth_interval_start"]
        constraints = BaseDepthInterval.constraints("soil_data")

    @classmethod
    def soil_inputs(cls):
        return [field.name for field in cls._meta.fields if field.name.endswith("_enabled")]

    def clean(self):
        super().clean()
        BaseDepthInterval.validate_intervals(list(self.soil_data.depth_intervals.all()))

    soil_texture_enabled = models.BooleanField(blank=True, null=True)
    soil_color_enabled = models.BooleanField(blank=True, null=True)
    soil_structure_enabled = models.BooleanField(blank=True, null=True)
    carbonates_enabled = models.BooleanField(blank=True, null=True)
    ph_enabled = models.BooleanField(blank=True, null=True)
    soil_organic_carbon_matter_enabled = models.BooleanField(blank=True, null=True)
    electrical_conductivity_enabled = models.BooleanField(blank=True, null=True)
    sodium_adsorption_ratio_enabled = models.BooleanField(blank=True, null=True)
