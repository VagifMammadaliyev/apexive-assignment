# Generated by Django 3.0 on 2020-05-30 18:10

from django.conf import settings
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0005_auto_20200530_1954'),
        ('fulfillment', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
                ('purpose', models.CharField(choices=[('order_payment', 'Sifariş ödənişi'), ('declaration_payment', 'Bəyənnamə ödənişi'), ('order_remainder_payment', 'Sifariş qalığı ödənişi'), ('order_refund', 'Sifarişin geri ödənişi'), ('declaration_refund', 'Bəyənnamənin geri ödənişi'), ('balance_increase', 'Balans artırılması'), ('balance_decrease', 'Balansdan çıxarış')], max_length=30)),
                ('type', models.CharField(choices=[('card', 'Kart'), ('cash', 'Nağd')], max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('extra', django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict, null=True)),
                ('currency', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.Currency')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', related_query_name='transaction', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'transaction',
            },
        ),
    ]
