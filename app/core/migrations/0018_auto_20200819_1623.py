# Generated by Django 3.0 on 2020-08-19 12:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_auto_20200819_1621'),
    ]

    operations = [
        migrations.AddField(
            model_name='city',
            name='is_default_source',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='country',
            name='is_default_source',
            field=models.BooleanField(default=False),
        ),
    ]
