# Generated by Django 3.1.2 on 2020-10-21 22:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0253_auto_20201020_1737'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipment',
            name='extra',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]