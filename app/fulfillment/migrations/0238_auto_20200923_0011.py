# Generated by Django 3.1.1 on 2020-09-22 20:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0237_auto_20200922_2227'),
    ]

    operations = [
        migrations.AddField(
            model_name='productcategory',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='producttype',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]
