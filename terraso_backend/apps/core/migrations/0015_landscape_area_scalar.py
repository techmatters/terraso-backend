# Generated by Django 4.1.3 on 2022-11-15 16:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_group_membership_type_membership_membership_status_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="landscape",
            name="area_scalar_m2",
            field=models.FloatField(blank=True, null=True),
        )
    ]
