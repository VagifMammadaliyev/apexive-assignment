# Generated by Django 3.0 on 2020-06-14 11:06

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0034_order_user_note'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='product_category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orders', related_query_name='orders', to='fulfillment.ProductCategory'),
        ),
        migrations.AddField(
            model_name='package',
            name='product_category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='packages', related_query_name='package', to='fulfillment.ProductCategory'),
        ),
    ]
