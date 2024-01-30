# Generated by Django 3.0 on 2020-08-29 16:09

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0029_auto_20200829_2009'),
        ('fulfillment', '0186_addressfield_append_user_full_name'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='courierorder',
            name='destination_address',
        ),
        migrations.RemoveField(
            model_name='order',
            name='destination_user_address',
        ),
        migrations.RemoveField(
            model_name='shipment',
            name='destination_user_address',
        ),
        migrations.AddField(
            model_name='courierorder',
            name='recipient',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='courier_orders', related_query_name='courier_order', to='customer.Recipient'),
        ),
        migrations.AddField(
            model_name='order',
            name='recipient',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orders', related_query_name='order', to='customer.Recipient'),
        ),
        migrations.AddField(
            model_name='shipment',
            name='recipient',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='shipments', related_query_name='shipment', to='customer.Recipient'),
        ),
    ]
