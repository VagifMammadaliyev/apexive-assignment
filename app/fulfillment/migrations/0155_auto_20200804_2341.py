# Generated by Django 3.0 on 2020-08-04 19:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0154_auto_20200804_2204'),
    ]

    operations = [
        migrations.AddField(
            model_name='warehouse',
            name='does_consider_volume',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='warehouse',
            name='does_serve_dangerous_packages',
            field=models.BooleanField(default=False),
        ),
    ]
