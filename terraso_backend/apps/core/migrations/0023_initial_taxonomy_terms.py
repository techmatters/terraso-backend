# Generated by Django 4.1 on 2022-11-01 19:45

import uuid

from django.db import migrations
from django.utils.text import slugify

TERMS = {
    "ecosystem-type": [
        "Deserts",
        "Forest, Temperate",
        "Forest, Tropical",
        "Marine/coastal",
        "Polar/Alpine",
        "Savannas",
        "Shrublands",
        "Wetlands",
    ],
    "livelihood": [
        "Crop farming",
        "Cattle and livestock farming",
        "Education",
        "Fishing",
        "Forest management",
        "Mineral mining",
        "Industry",
        "Timber",
        "Eco-tourism",
        "Service industry",
        "Trade and commerce",
        "Wage earners",
        "Other",
    ],
    "commodity": [
        "Almond",
        "Apple",
        "Aromatic oil",
        "Cashew",
        "Cassava",
        "Cattle",
        "Coal",
        "Coffee",
        "Compost",
        "Cotton",
        "Fodder for livestock",
        "Goat",
        "Gold",
        "Herbal medicine",
        "Honey",
        "Lamb",
        "Mezcal",
        "Minerals",
        "Olive oil",
        "Other",
        "Other, fruit",
        "Other, vegetable",
        "Palm oil",
        "Peanut",
        "Pear",
        "Pepper",
        "Resins",
        "Rice",
        "Rubber",
        "Sheep",
        "Soy",
        "Sugar",
        "Tea",
        "Timber",
        "Water",
        "Wine",
    ],
}


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0022_landscape_development_strategy"),
    ]

    operations = [
        migrations.RunSQL(sql="DELETE FROM core_landscape_taxonomy_terms;"),
        migrations.RunSQL(sql="DELETE FROM core_taxonomyterm;"),
    ] + [
        migrations.RunSQL(
            sql=[
                (
                    "INSERT INTO core_taxonomyterm (id, deleted_by_cascade, created_at, updated_at, slug, type, value_original, value_en, value_es) VALUES (%s, false, NOW(), NOW(), %s, %s, %s, '', '');",
                    [uuid.uuid4(), slugify(value), type, value],
                )
            ],
        )
        for type, values in TERMS.items()
        for value in values
    ]
