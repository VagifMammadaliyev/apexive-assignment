# Generated by Django 3.1.1 on 2020-09-08 20:57

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0030_auto_20200908_2301'),
        ('fulfillment', '0214_auto_20200908_0527'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='courierarea',
            name='discounted_price',
        ),
        migrations.RemoveField(
            model_name='courierarea',
            name='price',
        ),
        migrations.RemoveField(
            model_name='courierarea',
            name='price_currency',
        ),
        migrations.CreateModel(
            name='CourierTariff',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('title_az', models.CharField(max_length=255, null=True)),
                ('title_ru', models.CharField(max_length=255, null=True)),
                ('title_en', models.CharField(max_length=255, null=True)),
                ('price', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
                ('discounted_price', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
                ('area', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tariffs', related_query_name='tariff', to='fulfillment.courierarea')),
                ('price_currency', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.currency')),
            ],
            options={
                'db_table': 'courier_tariff',
            },
        ),
    ]
