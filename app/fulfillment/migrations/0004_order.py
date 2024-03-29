# Generated by Django 3.0 on 2020-05-31 16:08

from django.conf import settings
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0005_auto_20200530_1954'),
        ('fulfillment', '0003_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tracking_code', models.CharField(db_index=True, max_length=20, unique=True)),
                ('product_url', models.URLField(blank=True, max_length=255, null=True)),
                ('product_price', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
                ('real_product_price', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
                ('cargo_price', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
                ('real_cargo_price', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
                ('product_quantity', models.PositiveIntegerField(default=1)),
                ('real_product_quantity', models.PositiveIntegerField(default=1)),
                ('user_comment', models.CharField(max_length=140)),
                ('is_paid', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('extra', django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict, null=True)),
                ('source_country', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.Country')),
                ('status', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='related_orders', related_query_name='related_order', to='fulfillment.Status')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orders', related_query_name='order', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'order',
            },
        ),
    ]
