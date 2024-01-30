# Generated by Django 3.0 on 2020-07-17 11:57

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0128_queue_last_queue_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipment',
            name='queued_item',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='shipments', related_query_name='shipment', to='fulfillment.QueuedItem'),
        ),
    ]