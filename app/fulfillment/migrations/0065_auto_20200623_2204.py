# Generated by Django 3.0 on 2020-06-23 18:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0064_auto_20200623_1731'),
    ]

    operations = [
        migrations.AddField(
            model_name='statusevent',
            name='message',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AddField(
            model_name='statusevent',
            name='message_az',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AddField(
            model_name='statusevent',
            name='message_ru',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
    ]