# Generated by Django 3.0 on 2020-08-24 14:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0026_auto_20200816_1624'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='client_code',
            field=models.CharField(db_index=True, max_length=20, unique=True),
        ),
    ]
