# Generated by Django 3.0 on 2020-08-29 19:07

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0032_frozenrecipient'),
    ]

    operations = [
        migrations.AddField(
            model_name='frozenrecipient',
            name='real_recipient',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='frozen_copies', related_query_name='frozen_copy', to='customer.Recipient'),
        ),
    ]
