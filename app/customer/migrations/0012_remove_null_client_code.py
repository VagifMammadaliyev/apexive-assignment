# Generated by Django 3.0 on 2020-06-09 15:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0011_populate_client_codes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='client_code',
            field=models.CharField(db_index=True, max_length=10, unique=True),
        ),
    ]
