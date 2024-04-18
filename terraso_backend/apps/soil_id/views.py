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

import json
import os

from django.conf import settings
from django.http import JsonResponse
from django.views import View


class SoilIdList(View):
    def get(self, request, *args, **kwargs):
        # lat = request.GET.get("lat")
        # lng = request.GET.get("lng")
        # plot_id = request.GET.get("plot_id")

        with open(os.path.join(settings.BASE_DIR, "apps/soil_id/data/list.json")) as json_data:
            data = json.load(json_data)

        return JsonResponse({"status": "ok", "data": data})


class SoilIdRank(View):
    def get(self, request, *args, **kwargs):

        with open(os.path.join(settings.BASE_DIR, "apps/soil_id/data/rank.json")) as json_data:
            data = json.load(json_data)

        return JsonResponse({"status": "ok", "data": data})
