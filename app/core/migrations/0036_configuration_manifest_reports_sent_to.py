# Generated by Django 3.1.1 on 2020-09-12 17:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_configuration_manifest_company_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuration',
            name='manifest_reports_sent_to',
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
    ]