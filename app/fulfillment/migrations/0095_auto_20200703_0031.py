# Generated by Django 3.0 on 2020-07-02 20:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0094_auto_20200703_0018'),
    ]

    operations = [
        migrations.AlterField(
            model_name='package',
            name='shelf',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]