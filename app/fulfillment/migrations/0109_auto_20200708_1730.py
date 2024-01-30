# Generated by Django 3.0 on 2020-07-08 13:30

from django.db import migrations, models
import django.db.models.deletion
import fulfillment.models.service


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_auto_20200610_1725'),
        ('fulfillment', '0108_remove_shipment_payment_method'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdditionalService',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('for_packages', 'Bağlamalar üçün'), ('for_shipment', 'Göndərmələr üçün')], max_length=15)),
                ('title', models.CharField(max_length=512)),
                ('description', models.TextField()),
                ('needs_attachment', models.BooleanField(default=False)),
                ('price', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
            ],
            options={
                'db_table': 'additional_service',
            },
        ),
        migrations.CreateModel(
            name='ShipmentAdditionalService',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attachment', models.FileField(blank=True, null=True, upload_to=fulfillment.models.service.get_shipment_service_attachment_path)),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='fulfillment.AdditionalService')),
                ('shipment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='fulfillment.Shipment')),
            ],
            options={
                'db_table': 'shipment_service',
            },
        ),
        migrations.CreateModel(
            name='PackageAdditionalService',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attachment', models.FileField(blank=True, null=True, upload_to=fulfillment.models.service.get_shipment_service_attachment_path)),
                ('package', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='fulfillment.Package')),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='fulfillment.AdditionalService')),
            ],
            options={
                'db_table': 'package_service',
            },
        ),
        migrations.AddField(
            model_name='additionalservice',
            name='packages',
            field=models.ManyToManyField(related_name='services', related_query_name='service', through='fulfillment.PackageAdditionalService', to='fulfillment.Package'),
        ),
        migrations.AddField(
            model_name='additionalservice',
            name='price_currency',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.Currency'),
        ),
        migrations.AddField(
            model_name='additionalservice',
            name='shipments',
            field=models.ManyToManyField(related_name='services', related_query_name='service', through='fulfillment.ShipmentAdditionalService', to='fulfillment.Shipment'),
        ),
    ]