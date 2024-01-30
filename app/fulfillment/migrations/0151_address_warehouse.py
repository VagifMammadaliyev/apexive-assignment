# Generated by Django 3.0 on 2020-08-04 17:56

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0150_auto_20200802_0057'),
    ]

    operations = [
        migrations.AddField(
            model_name='address',
            name='warehouse',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='foreign_address', to='fulfillment.Address'),
        ),
    ]
