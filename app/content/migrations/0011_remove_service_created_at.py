# Generated by Django 3.0 on 2020-06-22 19:43

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0010_auto_20200614_0035'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='service',
            name='created_at',
        ),
    ]
