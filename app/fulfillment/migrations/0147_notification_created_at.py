# Generated by Django 3.0 on 2020-07-31 19:32

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0146_auto_20200731_2329'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
