# Generated by Django 3.1.1 on 2020-09-22 18:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0040_onlineshoppingdomain'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuration',
            name='address_on_invoice',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='configuration',
            name='email_address_on_invoice',
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
    ]
