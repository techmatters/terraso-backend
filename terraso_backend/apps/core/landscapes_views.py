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

from django.http import JsonResponse
from django.views import View

from .models import Landscape


class LandscapeExportView(View):
    def get(self, request, slug, format):
        if format != "json":
            return JsonResponse({"error": "Format not supported"}, status=400)
        try:
            landscape = Landscape.objects.get(slug=slug)
            json = self.to_json(landscape)
            return JsonResponse(json, status=200)
        except Landscape.DoesNotExist:
            return JsonResponse({"error": "Landscape not found"}, status=404)

    def to_json(self, landscape):
        development_strategy = landscape.associated_development_strategy.last()
        terms = landscape.taxonomy_terms.all()
        associated_groups = landscape.associated_groups.exclude(is_default_landscape_group=True)
        groups = [associated_group.group for associated_group in associated_groups]

        # Get most recent last updated date from landscape, development strategy, terms and groups
        last_updated = max(
            [
                landscape.updated_at.timestamp(),
                development_strategy.updated_at.timestamp() if development_strategy else 0,
                max([term.updated_at.timestamp() for term in terms]) if terms else 0,
                max([group.updated_at.timestamp() for group in groups]) if groups else 0,
            ]
        )

        return {
            "id": str(landscape.id),
            "name": landscape.name,
            "description": landscape.description,
            "region": landscape.location,
            "publicContactEmail": landscape.email,
            "website": landscape.website,
            "areaPolygon": landscape.area_polygon,
            "areaTypes": landscape.area_types,
            "areaScalarHa": landscape.area_scalar_m2 / 10000 if landscape.area_scalar_m2 else None,
            "population": landscape.population,
            "profileImage": landscape.profile_image,
            "profileImageDescription": landscape.profile_image_description,
            "taxonomyTerms": [
                {
                    "type": term.type,
                    "value": {
                        "original": term.value_original,
                        "en": term.value_en,
                        "es": term.value_es,
                    },
                }
                for term in terms
            ],
            "associatedGroups": list(set([group.name for group in groups])),
            "developmentStrategy": {
                "objectives": development_strategy.objectives,
                "problemSituation": development_strategy.problem_situtation,
                "interventionStrategy": development_strategy.intervention_strategy,
                "opportunities": development_strategy.opportunities,
            }
            if development_strategy
            else None,
            "lastUpdated": last_updated,
        }
