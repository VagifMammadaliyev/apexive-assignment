# Generated by Django 3.0 on 2020-08-07 13:16

import ckeditor_uploader.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0020_auto_20200807_1658'),
    ]

    operations = [
        migrations.CreateModel(
            name='SitePreset',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100)),
                ('about_text', ckeditor_uploader.fields.RichTextUploadingField(blank=True, null=True)),
                ('about_text_az', ckeditor_uploader.fields.RichTextUploadingField(blank=True, null=True)),
                ('about_text_ru', ckeditor_uploader.fields.RichTextUploadingField(blank=True, null=True)),
                ('main_office_address', models.TextField(blank=True, null=True)),
                ('main_office_address_az', models.TextField(blank=True, null=True)),
                ('main_office_address_ru', models.TextField(blank=True, null=True)),
                ('emails', models.TextField(blank=True, help_text='Example: "support@ontime.az, help@ontime.az" without quotes', null=True)),
                ('phone_numbers', models.TextField(blank=True, help_text='Example: "+9945555555, +994515555555" without quotes', null=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'db_table': 'site_preset',
            },
        ),
    ]
