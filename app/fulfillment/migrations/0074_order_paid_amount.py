# Generated by Django 3.0 on 2020-06-27 22:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0073_auto_20200627_2357'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='paid_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=9),
        ),
    ]
