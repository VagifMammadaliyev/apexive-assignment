# Generated by Django 3.0 on 2020-08-25 23:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_auto_20200825_1006'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuration',
            name='password_reset_url',
            field=models.URLField(blank=True, help_text='Front app URL for resetring user password', null=True),
        ),
    ]
