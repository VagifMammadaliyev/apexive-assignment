# Generated by Django 3.1.6 on 2021-06-03 10:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0050_configuration_paytr_redirect_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuration',
            name='smart_customs_declarations_window_in_days',
            field=models.IntegerField(default=15),
        ),
    ]