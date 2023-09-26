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

import pytest

pytestmark = pytest.mark.django_db


def test_terms_query(client_query, taxonomy_terms):
    response = client_query(
        """
        {taxonomyTerms {
          edges {
            node {
              valueOriginal
            }
          }
        }}
        """
    )
    edges = response.json()["data"]["taxonomyTerms"]["edges"]
    result = [edge["node"]["valueOriginal"] for edge in edges]

    for term in taxonomy_terms:
        assert term.value_original in result


def test_landscape_get_one_by_type(client_query, taxonomy_terms):
    query = """
        {taxonomyTerms(type_In: [LANGUAGE]) {
          edges {
            node {
              valueOriginal
            }
          }
        }}
        """
    response = client_query(query)
    result = response.json()["data"]["taxonomyTerms"]["edges"]
    language_terms = [term for term in taxonomy_terms if term.type == "LANGUAGE"]

    assert len(result) == len(language_terms)
