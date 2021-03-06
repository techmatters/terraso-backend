# Generated by Django 3.2.11 on 2022-01-18 22:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_alter_group_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="group",
            name="deleted_at",
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="groupassociation",
            name="deleted_at",
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="landscape",
            name="deleted_at",
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="landscapegroup",
            name="deleted_at",
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="membership",
            name="deleted_at",
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="deleted_at",
            field=models.DateTimeField(editable=False, null=True),
        ),
    ]
