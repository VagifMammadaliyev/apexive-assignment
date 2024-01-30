# Generated by Django 3.0 on 2020-06-11 17:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_auto_20200610_1725'),
        ('fulfillment', '0026_auto_20200610_1843'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tariff',
            name='country',
        ),
        migrations.AddField(
            model_name='tariff',
            name='destination_city',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='destination_tariffs', related_query_name='destination_tariff', to='core.City'),
        ),
        migrations.AddField(
            model_name='tariff',
            name='destination_country',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='destination_tariffs', related_query_name='destination+tariff', to='core.Country'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='tariff',
            name='source_city',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='source_tariffs', related_query_name='source_tariff', to='core.City'),
        ),
        migrations.AddField(
            model_name='tariff',
            name='source_country',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='source_tariffs', related_query_name='source_tariff', to='core.Country'),
            preserve_default=False,
        ),
    ]