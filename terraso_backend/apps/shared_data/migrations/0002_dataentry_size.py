# Generated by Django 4.0.4 on 2022-05-16 16:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shared_data", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="dataentry",
            name="size",
            field=models.PositiveBigIntegerField(null=True),
        ),
    ]
