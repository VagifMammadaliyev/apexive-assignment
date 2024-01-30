# Generated by Django 3.0 on 2020-07-17 10:55

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('customer', '0020_user_is_created_by_admin'),
        ('fulfillment', '0126_auto_20200715_2027'),
    ]

    operations = [
        migrations.CreateModel(
            name='Queue',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50)),
                ('type', models.CharField(choices=[('cashier', 'Kassir növbəsi'), ('whman', 'Anbardar növbəsi')], max_length=10)),
                ('warehouse', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='queues', related_query_name='queue', to='fulfillment.Warehouse')),
            ],
            options={
                'db_table': 'queue',
                'unique_together': {('code', 'warehouse')},
            },
        ),
        migrations.CreateModel(
            name='QueuedItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=100)),
                ('ready', models.BooleanField(default=False)),
                ('queue', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='queued_items', related_query_name='queued_item', to='fulfillment.Queue')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='queued_items', related_query_name='queued_item', to='customer.Customer')),
            ],
            options={
                'db_table': 'queued_item',
                'unique_together': {('code', 'queue')},
            },
        ),
        migrations.CreateModel(
            name='Monitor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('for_queue', 'Növbə üçün'), ('for_customer', 'Müştəri üçün')], max_length=15)),
                ('code', models.CharField(max_length=100)),
                ('auth', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='as_monitor', to=settings.AUTH_USER_MODEL)),
                ('queue', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='fulfillment.Queue')),
                ('warehouse', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='fulfillment.Warehouse')),
            ],
            options={
                'db_table': 'monitor',
                'unique_together': {('code', 'warehouse', 'queue')},
            },
        ),
    ]