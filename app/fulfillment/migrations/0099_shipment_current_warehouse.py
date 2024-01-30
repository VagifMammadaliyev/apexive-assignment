# Generated by Django 3.0 on 2020-07-03 19:35

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0098_shipment_shelf'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipment',
            name='current_warehouse',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='current_shipments', related_query_name='current_shipment', to='fulfillment.Warehouse'),
        ),
    ]
