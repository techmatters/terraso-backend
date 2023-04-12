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
import json

import pytest

from apps.project_management.models import Site

pytestmark = pytest.mark.django_db


def test_site_creation(client_query, user):
    lat = 0
    lon = 0
    site_name = "Test Site"
    response = client_query(
        """
    mutation createSite($input: SiteAddMutationInput!) {
        siteAddMutation(input: $input) {
           site {
              id
           }
        }
    }
""",
        variables={"input": {"latitude": lat, "longitude": lon, "name": site_name}},
    )
    content = json.loads(response.content)
    assert "errors" not in content
    id = content["data"]["siteAddMutation"]["site"]["id"]
    site = Site.objects.get(pk=id)
    assert str(site.id) == id
    assert site.latitude == pytest.approx(site.latitude)
    assert site.longitude == pytest.approx(site.longitude)
    assert site.creator == user
