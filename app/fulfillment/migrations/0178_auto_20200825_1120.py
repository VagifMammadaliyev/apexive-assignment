# Generated by Django 3.0 on 2020-08-25 07:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0177_auto_20200825_1006'),
    ]

    operations = [
        migrations.AlterField(
            model_name='status',
            name='type',
            field=models.CharField(choices=[('order_statuses', 'Sifarişlər üçün'), ('package_statuses', 'Bağlamalar üçün'), ('shipment_statuses', 'Göndərmələr üçün'), ('courier_order_statuses', 'Kuryer sifarişləri üçün')], max_length=30),
        ),
    ]