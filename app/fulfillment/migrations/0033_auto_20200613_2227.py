# Generated by Django 3.0 on 2020-06-13 18:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0032_auto_20200613_2205'),
    ]

    operations = [
        migrations.AlterField(
            model_name='package',
            name='tracking_code',
            field=models.CharField(db_index=True, max_length=40, unique=True),
        ),
    ]