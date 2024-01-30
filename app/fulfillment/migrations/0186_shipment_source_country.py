# Generated by Django 3.0 on 2020-08-29 12:30

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_country_flag_image'),
        ('fulfillment', '0185_ticketcomment_is_by_customer_service'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipment',
            name='source_country',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='core.Country'),
        ),
    ]
