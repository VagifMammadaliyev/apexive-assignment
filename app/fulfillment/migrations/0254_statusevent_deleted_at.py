# Generated by Django 3.1.2 on 2020-10-16 05:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0253_auto_20201016_0813'),
    ]

    operations = [
        migrations.AddField(
            model_name='statusevent',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
