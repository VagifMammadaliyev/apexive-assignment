# Generated by Django 3.0 on 2020-07-12 14:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0123_auto_20200712_1643'),
    ]

    operations = [
        migrations.AddField(
            model_name='warehouse',
            name='is_consolidation_enabled',
            field=models.BooleanField(default=False),
        ),
    ]
