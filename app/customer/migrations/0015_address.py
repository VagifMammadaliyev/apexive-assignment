# Generated by Django 3.0 on 2020-06-20 09:52

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_auto_20200610_1725'),
        ('customer', '0014_user_role'),
    ]

    operations = [
        migrations.CreateModel(
            name='Address',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=50)),
                ('region', models.CharField(max_length=100)),
                ('district', models.CharField(blank=True, max_length=100, null=True)),
                ('city', models.CharField(max_length=100)),
                ('zip_code', models.CharField(max_length=15)),
                ('street_name', models.CharField(max_length=100)),
                ('house_numbers', models.CharField(max_length=10)),
                ('unit_number', models.CharField(max_length=15)),
                ('recipient_first_name', models.CharField(max_length=30)),
                ('recipient_last_name', models.CharField(max_length=30)),
                ('recipient_phone_number', models.CharField(max_length=15)),
                ('country', models.ForeignKey(limit_choices_to={'is_base': True}, on_delete=django.db.models.deletion.PROTECT, related_name='user_addresses', related_query_name='user_address', to='core.Country')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='addresses', related_query_name='address', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'user_address',
            },
        ),
    ]
