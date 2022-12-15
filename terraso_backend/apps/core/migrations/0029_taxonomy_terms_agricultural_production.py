import uuid

from django.db import migrations
from django.utils.text import slugify

TERMS = [
    ("Aeroponic", "Aeropónico"),
    ("Agroecological", "Agroecológico"),
    ("Agroforestry", "Agroforestal"),
    ("Aquaponic", "Acuaponia"),
    ("Biodynamic", "Biodinámico"),
    ("Climate-Smart Agriculture", "Agricultura climáticamente inteligente"),
    ("Commercial farming", "Agricultura comercial"),
    ("Conventional", "Convencional"),
    ("Hydroponic", "Hidropónico"),
    ("Monoculture", "Monocultivo"),
    ("Organic", "Orgánico"),
    ("Permaculture", "Permacultura"),
    ("Polyculture", "Policultivo"),
    ("Silvoforest", "Silvoforestal"),
    ("Subsistance farming", "Agricultura de subsistencia"),
    ("Sustainable agriculture", "Agricultura sostenible"),
    ("Vertical farming", "Agricultura vertical"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0028_spanish_taxonomy_terms"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                (
                    """
                    INSERT INTO core_taxonomyterm (id, deleted_by_cascade, created_at, updated_at, slug, type, value_original, value_en, value_es)
                    VALUES (%s, false, NOW(), NOW(), %s, %s, %s, %s, %s);
                    """,
                    [
                        uuid.uuid4(),
                        slugify(value_en),
                        "agricultural-production-method",
                        value_en,
                        value_en,
                        value_es,
                    ],
                )
            ],
        )
        for (value_en, value_es) in TERMS
    ]
