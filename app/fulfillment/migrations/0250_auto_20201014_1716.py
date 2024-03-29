# Generated by Django 3.1.2 on 2020-10-14 13:16

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('fulfillment', '0249_orderedproduct_is_visible'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderedproduct',
            name='order',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='fulfillment.order'),
        ),
        migrations.AddField(
            model_name='orderedproduct',
            name='shipment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='fulfillment.shipment'),
        ),
        migrations.AlterField(
            model_name='orderedproduct',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
    ]
