# Generated by Django 3.0 on 2020-06-06 12:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0017_package_external_tracking_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='package',
            name='user_comment',
            field=models.CharField(blank=True, max_length=140, null=True),
        ),
    ]
