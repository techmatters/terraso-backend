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
        ("core", "0030_alter_landscape_partnership_status"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                (
                    """
                    INSERT INTO core_taxonomyterm (id, deleted_by_cascade, created_at, updated_at, slug, type, value_original, value_en, value_es)
                    SELECT %s, false, NOW(), NOW(), %s, %s, %s, %s, %s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM core_taxonomyterm
                        WHERE type = %s AND value_original = %s
                    )
                    """,
                    [
                        uuid.uuid4(),
                        slugify(value_en),
                        "agricultural-production-method",
                        value_en,
                        value_en,
                        value_es,
                        "agricultural-production-method",
                        value_en,
                    ],
                )
            ],
        )
        for (value_en, value_es) in TERMS
    ]
