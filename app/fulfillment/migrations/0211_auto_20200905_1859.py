# Generated by Django 3.0 on 2020-09-05 14:59

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0210_auto_20200905_1839'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='address',
            options={'verbose_name_plural': 'Addresses'},
        ),
        migrations.RemoveField(
            model_name='address',
            name='display_order',
        ),
    ]
