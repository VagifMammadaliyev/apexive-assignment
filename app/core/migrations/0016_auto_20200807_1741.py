# Generated by Django 3.0 on 2020-08-07 13:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_auto_20200807_1731'),
    ]

    operations = [
        migrations.AlterField(
            model_name='configuration',
            name='order_commission_info_text',
            field=models.TextField(blank=True, help_text='Text that will be shown to user on order create page', null=True),
        ),
        migrations.AlterField(
            model_name='configuration',
            name='order_commission_info_text_az',
            field=models.TextField(blank=True, help_text='Text that will be shown to user on order create page', null=True),
        ),
        migrations.AlterField(
            model_name='configuration',
            name='order_commission_info_text_ru',
            field=models.TextField(blank=True, help_text='Text that will be shown to user on order create page', null=True),
        ),
    ]
