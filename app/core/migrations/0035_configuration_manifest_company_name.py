# Generated by Django 3.1.1 on 2020-09-09 13:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_auto_20200909_1456'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuration',
            name='manifest_company_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
