# Generated by Django 3.0 on 2020-07-22 13:12

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('fulfillment', '0133_auto_20200719_1247'),
    ]

    operations = [
        migrations.AlterField(
            model_name='queueditem',
            name='linked_warehouseman_item',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='linked_cashier_item', to='fulfillment.QueuedItem'),
        ),
        migrations.CreateModel(
            name='CustomerServiceProfile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.OneToOneField(limit_choices_to={'is_staff': True}, on_delete=django.db.models.deletion.CASCADE, related_name='customer_service_profile', to=settings.AUTH_USER_MODEL)),
                ('warehouse', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='customer_service_workers', related_query_name='customer_service_worker', to='fulfillment.Warehouse')),
            ],
            options={
                'db_table': 'customer_service',
                'unique_together': {('user', 'warehouse')},
            },
        ),
    ]