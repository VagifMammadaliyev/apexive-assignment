# Generated by Django 3.0 on 2020-07-25 17:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_auto_20200725_0244'),
    ]

    operations = [
        migrations.CreateModel(
            name='Configuration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='Just a human readable title for your configuration', max_length=255)),
                ('order_commission_percentage', models.DecimalField(decimal_places=2, default=5, max_digits=9)),
                ('minimum_order_commission_price', models.DecimalField(decimal_places=2, default=2, help_text='If commission calculated using percentage is less than value specified here then use this value instead of calculated.', max_digits=9)),
                ('minimum_order_commission_price_currency', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.Currency')),
            ],
            options={
                'db_table': 'configuration',
            },
        ),
    ]
