# Generated by Django 3.0 on 2020-06-29 17:27

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0077_auto_20200629_2112'),
    ]

    operations = [
        migrations.AlterField(
            model_name='warehousemanprofile',
            name='warehouse',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='warehousemen', related_query_name='warehousemen', to='fulfillment.Warehouse'),
        ),
    ]
