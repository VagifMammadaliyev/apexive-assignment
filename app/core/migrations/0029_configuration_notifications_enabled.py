# Generated by Django 3.0 on 2020-09-06 12:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_auto_20200906_1356'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuration',
            name='notifications_enabled',
            field=models.BooleanField(default=True),
        ),
    ]