# Generated by Django 3.0 on 2020-07-01 14:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0090_auto_20200701_1823'),
    ]

    operations = [
        migrations.AlterField(
            model_name='box',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
