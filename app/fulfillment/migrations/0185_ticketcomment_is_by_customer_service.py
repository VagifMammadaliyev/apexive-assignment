# Generated by Django 3.0 on 2020-08-28 16:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0184_remove_status_is_public'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticketcomment',
            name='is_by_customer_service',
            field=models.BooleanField(default=False),
        ),
    ]
