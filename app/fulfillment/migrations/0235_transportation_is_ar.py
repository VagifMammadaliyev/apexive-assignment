# Generated by Django 3.1.1 on 2020-09-19 19:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0234_auto_20200919_1602'),
    ]

    operations = [
        migrations.AddField(
            model_name='transportation',
            name='is_ar',
            field=models.BooleanField(default=False),
        ),
    ]
