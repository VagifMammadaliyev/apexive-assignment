# Generated by Django 3.0 on 2020-06-18 18:16

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0052_auto_20200618_1915'),
    ]

    operations = [
        migrations.RenameField(
            model_name='shipment',
            old_name='upadted_at',
            new_name='updated_at',
        ),
    ]