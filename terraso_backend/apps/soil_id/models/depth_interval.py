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

from typing import List, Self

from django.core.validators import MaxValueValidator
from django.db import models
from django.forms import ValidationError


class BaseDepthInterval(models.Model):
    depth_interval_start = models.PositiveIntegerField(blank=True)
    depth_interval_end = models.PositiveIntegerField(
        blank=True, validators=[MaxValueValidator(200)]
    )

    class Meta:
        abstract = True

    @staticmethod
    def constraints(related_field: str):
        return [
            models.UniqueConstraint(
                fields=[related_field, "depth_interval_start", "depth_interval_end"],
                name="%(app_label)s_%(class)s_unique_depth_interval",
            ),
            models.CheckConstraint(
                check=models.Q(depth_interval_start__lt=models.F("depth_interval_end")),
                name="%(app_label)s_%(class)s_depth_interval_coherence",
            ),
        ]

    @staticmethod
    def validate_intervals(intervals: List[Self]):
        intervals.sort(key=lambda interval: interval.start)
        for index, interval in enumerate(intervals):
            if (
                index + 1 < len(intervals)
                and interval.depth_interval_end > intervals[index + 1].depth_interval_start
            ):
                raise ValidationError(
                    f"""
                    Depth interval must end at or before next interval,
                    got {interval} followed by {intervals[index + 1]}
                    """
                )
