# Generated by Django 3.2.15 on 2022-09-14 19:09

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("subscription", "0002_populate_plans"),
    ]

    operations = [
        migrations.RunSQL(
            r"DELETE FROM subscription_extrapackagetypejobminutes;",
            migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            r"DELETE FROM subscription_extrapackagetype WHERE code != 'storage_medium'",
            migrations.RunSQL.noop,
        ),
    ]
