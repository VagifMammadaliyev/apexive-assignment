# Generated by Django 3.0 on 2020-09-06 09:56

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_auto_20200906_1350'),
    ]

    operations = [
        migrations.AlterField(
            model_name='country',
            name='currency',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='core.Currency'),
        ),
    ]
