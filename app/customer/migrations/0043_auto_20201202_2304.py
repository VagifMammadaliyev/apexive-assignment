# Generated by Django 3.1.2 on 2020-12-02 19:04

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0042_commonpassword'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='commonpassword',
            name='user',
        ),
        migrations.AddField(
            model_name='commonpassword',
            name='extra',
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='commonpassword',
            name='generated_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
    ]
