# Generated by Django 3.0 on 2020-06-10 14:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_auto_20200610_1725'),
        ('fulfillment', '0025_auto_20200610_1326'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='commission_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=9),
        ),
        migrations.AddField(
            model_name='order',
            name='commission_price_currency',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.Currency'),
            preserve_default=False,
        ),
    ]
