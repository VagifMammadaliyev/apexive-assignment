# Generated by Django 3.1.1 on 2020-09-11 16:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0223_auto_20200910_2227'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='lang_code',
            field=models.CharField(blank=True, max_length=5, null=True),
        ),
    ]
