# Generated by Django 3.1.2 on 2020-12-02 18:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_auto_20200922_2207'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuration',
            name='common_password_expire_minutes',
            field=models.PositiveIntegerField(default=5),
        ),
        migrations.AddField(
            model_name='configuration',
            name='common_password_is_enabled',
            field=models.BooleanField(default=True),
        ),
    ]