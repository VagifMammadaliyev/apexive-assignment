# Generated by Django 3.0 on 2020-07-05 09:25

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0102_auto_20200705_0214'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='box',
            unique_together=set(),
        ),
    ]
