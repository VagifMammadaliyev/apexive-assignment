# Generated by Django 3.0 on 2020-07-08 12:29

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0019_address_is_deleted'),
        ('fulfillment', '0106_auto_20200705_2249'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='destination_user_address',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='customer.Address'),
        ),
        migrations.AddField(
            model_name='order',
            name='is_oneclick',
            field=models.BooleanField(default=True),
        ),
    ]
