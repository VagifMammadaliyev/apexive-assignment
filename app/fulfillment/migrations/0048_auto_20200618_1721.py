# Generated by Django 3.0 on 2020-06-18 13:21

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0009_auto_20200610_1725'),
        ('fulfillment', '0047_auto_20200617_0023'),
    ]

    operations = [
        migrations.RenameField(
            model_name='tariff',
            old_name='is_liquid',
            new_name='is_dangerous',
        ),
        migrations.AlterField(
            model_name='status',
            name='type',
            field=models.CharField(choices=[('order_statuses', 'Sifarişlər üçün'), ('package_statuses', 'Bağlamalar üçün'), ('shipment_statuses', 'Göndərmələr üçün')], max_length=20),
        ),
        migrations.CreateModel(
            name='Shipment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(db_index=True, max_length=30)),
                ('user_note', models.CharField(blank=True, max_length=140, null=True)),
                ('declared_price', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
                ('total_price', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
                ('declared_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('upadted_at', models.DateTimeField(auto_now=True)),
                ('declared_price_currency', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.Currency')),
                ('destination_warehouse', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='local_shipments', related_query_name='local_shipment', to='fulfillment.Warehouse')),
                ('source_warehouse', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='foreign_shipments', related_query_name='foreign_shipment', to='fulfillment.Warehouse')),
                ('status', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='related_shipments', related_query_name='related_shipment', to='fulfillment.Status')),
                ('total_price_currency', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.Currency')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shipments', related_query_name='shipment', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'shipment',
            },
        ),
        migrations.AddField(
            model_name='package',
            name='shipment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='packages', related_query_name='package', to='fulfillment.Shipment'),
        ),
    ]
