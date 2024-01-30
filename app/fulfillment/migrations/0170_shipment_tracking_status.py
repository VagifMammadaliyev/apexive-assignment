# Generated by Django 3.0 on 2020-08-19 19:54

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0169_auto_20200819_1956'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipment',
            name='tracking_status',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='related_shipments', related_query_name='related_shipment', to='fulfillment.TrackingStatus'),
        ),
    ]