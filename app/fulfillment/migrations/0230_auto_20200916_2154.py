# Generated by Django 3.1.1 on 2020-09-16 17:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0229_auto_20200915_1951'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='description',
            field=models.CharField(max_length=500),
        ),
        migrations.AlterField(
            model_name='order',
            name='product_description',
            field=models.CharField(blank=True, max_length=400, null=True),
        ),
        migrations.AlterField(
            model_name='shipment',
            name='user_note',
            field=models.CharField(blank=True, max_length=300, null=True),
        ),
    ]
