# Generated by Django 3.0 on 2020-07-05 10:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0104_box_total_weight'),
    ]

    operations = [
        migrations.AlterField(
            model_name='box',
            name='total_weight',
            field=models.DecimalField(decimal_places=3, default=0, max_digits=9),
        ),
    ]