# Generated by Django 3.0 on 2020-06-14 10:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0033_auto_20200613_2227'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='user_note',
            field=models.TextField(blank=True, null=True),
        ),
    ]