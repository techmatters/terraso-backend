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
    language_terms = [term for term in taxonomy_terms if term.type == "language"]

    assert len(result) == len(language_terms)
