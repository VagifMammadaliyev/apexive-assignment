# Generated by Django 3.0 on 2020-08-04 18:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0152_auto_20200804_2158'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='address',
            options={'ordering': ['display_order'], 'verbose_name_plural': 'Addresses'},
        ),
        migrations.AddField(
            model_name='address',
            name='display_order',
            field=models.IntegerField(default=0),
        ),
    ]
