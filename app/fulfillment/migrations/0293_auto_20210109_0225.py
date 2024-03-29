# Generated by Django 3.1.2 on 2021-01-08 22:25

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0292_auto_20210106_1518'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='order',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='related_orders', related_query_name='related_order', to='fulfillment.package'),
        ),
        migrations.AddField(
            model_name='product',
            name='order',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='fulfillment.order'),
        ),
    ]
