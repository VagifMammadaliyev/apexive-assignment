# Generated by Django 3.0 on 2020-06-21 20:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0018_auto_20200621_2006'),
    ]

    operations = [
        migrations.AddField(
            model_name='address',
            name='is_deleted',
            field=models.BooleanField(default=False),
        ),
    ]