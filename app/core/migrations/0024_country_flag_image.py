# Generated by Django 3.0 on 2020-08-28 22:14

import core.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_configuration_password_reset_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='country',
            name='flag_image',
            field=models.ImageField(blank=True, null=True, upload_to=core.models.get_flag_image),
        ),
    ]