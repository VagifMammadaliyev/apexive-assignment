# Generated by Django 3.1.2 on 2021-01-23 20:29

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0296_auto_20210122_1733'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='multiexpense',
            name='expense',
        ),
    ]
