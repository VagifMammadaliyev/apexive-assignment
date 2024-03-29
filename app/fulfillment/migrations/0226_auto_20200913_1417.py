# Generated by Django 3.1.1 on 2020-09-13 10:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0225_package_seller'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='transportation',
            name='packing_list',
        ),
        migrations.RemoveField(
            model_name='transportation',
            name='packing_list_last_export_time',
        ),
        migrations.AddField(
            model_name='transportation',
            name='xml_manifest',
            field=models.FileField(blank=True, null=True, upload_to='xml-manifests/%Y/%m/%d/'),
        ),
        migrations.AddField(
            model_name='transportation',
            name='xml_manifest_last_export_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
