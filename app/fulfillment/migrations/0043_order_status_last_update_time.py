# Generated by Django 3.0 on 2020-06-15 19:51

import datetime
from django.db import migrations, models
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0042_auto_20200615_2348'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='status_last_update_time',
            field=models.DateTimeField(auto_now_add=True, default=datetime.datetime(2020, 6, 15, 19, 51, 42, 33874, tzinfo=utc)),
            preserve_default=False,
        ),
    ]
