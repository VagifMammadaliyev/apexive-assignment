# Generated by Django 3.0 on 2020-07-17 20:38

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0130_queueditem_linked_warehouseman_item'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='queueditem',
            unique_together=set(),
        ),
    ]
