# Generated by Django 3.0 on 2020-08-07 21:51

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0159_shipmentreceiver'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='notification',
            name='email_sent_on',
        ),
    ]
