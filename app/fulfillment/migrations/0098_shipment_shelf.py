# Generated by Django 3.0 on 2020-07-03 18:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0097_auto_20200703_2203'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipment',
            name='shelf',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
