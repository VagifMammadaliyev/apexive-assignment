# Generated by Django 3.0 on 2020-09-06 09:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_country_display_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='country',
            name='is_ordering_enabled',
            field=models.BooleanField(default=True),
        ),
    ]
