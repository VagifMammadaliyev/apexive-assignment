# Generated by Django 3.0 on 2020-06-29 16:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0011_remove_service_created_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='announcement',
            name='preview',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='service',
            name='preview',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
    ]