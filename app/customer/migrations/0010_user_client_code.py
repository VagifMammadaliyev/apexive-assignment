# Generated by Django 3.0 on 2020-06-09 14:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0009_auto_20200531_0119'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='client_code',
            field=models.CharField(db_index=True, max_length=10, null=True, unique=True),
        ),
    ]
