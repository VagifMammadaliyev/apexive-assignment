# Generated by Django 3.0 on 2020-07-29 18:39

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_configuration_is_active'),
    ]

    operations = [
        migrations.CreateModel(
            name='CurrencyRateLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rate', models.DecimalField(decimal_places=4, max_digits=9)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('currency', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rate_logs', related_query_name='rate_log', to='core.Currency')),
            ],
            options={
                'db_table': 'currency_rate_log',
            },
        ),
    ]