from django.db import migrations, models

import apps.core.models.commons

TERMS = {
    "ecosystem-type": [
        ("Deserts", "Desiertos"),
        ("Forest, Temperate", "Bosque, Templado"),
        ("Forest, Tropical", "Bosque, Tropical"),
        ("Marine/Coastal", "Marino / costero"),
        ("Polar/Alpine", "Polar / alpino"),
        ("Savannas", "Sabanas"),
        ("Shrublands", "Matorrales"),
        ("Wetlands", "Humedales"),
    ],
    "livelihood": [
        ("Crop farming", "Cultivos agrícolas"),
        ("Cattle and livestock farming", "Ganadería"),
        ("Education", "Educación"),
        ("Fishing", "Pescar"),
        ("Forest management", "Gestión de bosques"),
        ("Mineral mining", "Minería de minerales"),
        ("Industry", "Industria"),
        ("Timber", "Madera"),
        ("Eco-tourism", "Ecoturismo"),
        ("Service industry", "Servicio Industrial"),
        ("Trade and commerce", "Comercio"),
        ("Wage earners", "Asalariados"),
        ("Other", "Otro"),
    ],
    "commodity": [
        ("Almond", "Almendra"),
        ("Apple", "Manzana"),
        ("Aromatic oil", "Aceite aromático"),
        ("Cashew", "Anacardo/Cajuil/Cashew"),
        ("Cassava", "Mandioca/Yuca"),
        ("Cattle", "Ganado"),
        ("Coal", "Carbón"),
        ("Coffee", "Café"),
        ("Compost", "Compostaje/Abono"),
        ("Cotton", "Algodón"),
        ("Fodder for livestock", "Forraje para el ganado"),
        ("Goat", "Cabra"),
        ("Gold", "Oro"),
        ("Herbal medicine", "Medicina herbaria"),
        ("Honey", "Miel de abeja"),
        ("Lamb", "Cordero"),
        ("Mezcal", "Mezcal"),
        ("Minerals", "Minerales"),
        ("Olive oil", "Aceite de oliva"),
        ("Other", "Otro"),
        ("Other, fruit", "Otro, fruta"),
        ("Other, vegetable", "Otro, vegetal"),
        ("Palm oil", "Aceite de palma"),
        ("Peanut", "Maní"),
        ("Pear", "Pera"),
        ("Pepper", "Pimienta"),
        ("Resins", "Resinas"),
        ("Rice", "Arroz"),
        ("Rubber", "Goma/Caucho/Hule"),
        ("Sheep", "Oveja"),
        ("Soy", "Soja/Soya"),
        ("Sugar", "Azúcar"),
        ("Tea", "Té"),
        ("Timber", "Madera"),
        ("Water", "Agua"),
        ("Wine", "Vino"),
    ],
}


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0026_calculate_polygon_areas"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                (
                    "UPDATE core_taxonomyterm SET value_es = %s WHERE value_original = %s",
                    [value_es, value_en],
                )
            ],
        )
        for type, values in TERMS.items()
        for (value_en, value_es) in values
    ]
