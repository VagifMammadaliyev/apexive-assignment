# Generated by Django 3.0 on 2020-08-06 19:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0157_auto_20200806_2300'),
    ]

    operations = [
        migrations.AddField(
            model_name='warehouse',
            name='is_universal',
            field=models.BooleanField(default=False),
        ),
    ]
