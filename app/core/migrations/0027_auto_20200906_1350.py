# Generated by Django 3.0 on 2020-09-06 09:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_country_is_ordering_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='country',
            name='is_packages_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='country',
            name='ordering_disabled_message',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='country',
            name='ordering_disabled_message_az',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='country',
            name='ordering_disabled_message_en',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='country',
            name='ordering_disabled_message_ru',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='country',
            name='packages_disabled_message',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='country',
            name='packages_disabled_message_az',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='country',
            name='packages_disabled_message_en',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='country',
            name='packages_disabled_message_ru',
            field=models.TextField(blank=True, null=True),
        ),
    ]