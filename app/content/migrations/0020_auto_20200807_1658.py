# Generated by Django 3.0 on 2020-08-07 12:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0019_footerelement'),
    ]

    operations = [
        migrations.AddField(
            model_name='footerelement',
            name='column_number',
            field=models.IntegerField(default=1),
        ),
        migrations.AddField(
            model_name='footerelement',
            name='order_in_column',
            field=models.IntegerField(default=1),
        ),
    ]
