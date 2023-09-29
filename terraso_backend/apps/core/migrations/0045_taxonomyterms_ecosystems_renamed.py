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

from django.db import migrations

TERMS_TYPES = [
    ("ecosystem-type", "ECOSYSTEM_TYPE"),
    ("language", "LANGUAGE"),
    ("livelihood", "LIVELIHOOD"),
    ("commodity", "COMMODITY"),
    ("organization", "ORGANIZATION"),
    ("agricultural-production-method", "AGRICULTURAL_PRODUCTION_METHOD"),
]

TERMS = {
    "ECOSYSTEM_TYPE": [
        ("Deserts", "Desert", "Desierto"),
        ("Savannas", "Savannah", "Sabana"),
        ("Shrublands", "Shrubland", "Matorrales"),
    ],
}


def fix_case_term_types(apps, schema_editor):
    TaxonomyTerm = apps.get_model("core", "TaxonomyTerm")
    Landscape = apps.get_model("core", "Landscape")
    for wrong_type, correct_type in TERMS_TYPES:
        wrong_terms = TaxonomyTerm.objects.filter(type=wrong_type).all()
        for wrong_term in wrong_terms:
            try:
                correct_term = TaxonomyTerm.objects.filter(
                    type=correct_type, slug=wrong_term.slug
                ).get()
            except TaxonomyTerm.DoesNotExist:
                correct_term = None
            if not correct_term:
                wrong_term.type = correct_type
                wrong_term.save()
            else:
                landscapes = Landscape.objects.filter(taxonomy_terms__in=[wrong_term]).all()
                for landscape in landscapes:
                    landscape.taxonomy_terms.remove(wrong_term)
                    landscape.taxonomy_terms.add(correct_term)
                wrong_term.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0044_notifications"),
    ]

    operations = [migrations.RunPython(fix_case_term_types)] + [
        migrations.RunSQL(
            sql=[
                (
                    """
                        UPDATE core_taxonomyterm
                        SET
                            value_es = %s,
                            value_original = %s,
                            value_en = %s
                        WHERE
                            value_original = %s AND
                            type = %s
                    """,
                    [value_es, value_en, value_en, current_value, type],
                )
            ],
        )
        for type, values in TERMS.items()
        for (current_value, value_en, value_es) in values
    ]
