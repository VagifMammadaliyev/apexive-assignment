# Generated by Django 3.0 on 2020-07-11 13:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0119_box_destination_warehouse'),
    ]

    operations = [
        migrations.AddField(
            model_name='warehouse',
            name='codename',
            field=models.CharField(default='BRAVO1', max_length=100),
            preserve_default=False,
        ),
    ]
