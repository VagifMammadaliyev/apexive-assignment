# Generated by Django 3.0 on 2020-06-13 20:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0012_remove_null_client_code'),
    ]

    operations = [
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('user', 'İstifadəçi'), ('admin', 'Admin'), ('cashier', 'Kassir'), ('warehouseman', 'Anbardar'), ('shopping_assistant', 'Alış-veriş köməkçisi'), ('content_manager', 'Kontent menecer')], max_length=20, unique=True)),
            ],
            options={
                'db_table': 'role',
            },
        ),
    ]