# Generated by Django 3.0 on 2020-06-27 23:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0074_order_paid_amount'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='related_object_identifier',
            field=models.CharField(blank=True, db_index=True, max_length=50, null=True),
        ),
    ]
