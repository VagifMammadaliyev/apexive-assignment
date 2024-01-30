# Generated by Django 3.0 on 2020-08-01 20:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0149_auto_20200801_1632'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='email_sent_on',
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='is_email_sent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='notification',
            name='is_sms_sent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='notification',
            name='sms_sent_on',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]