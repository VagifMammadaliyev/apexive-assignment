# Generated by Django 3.1.2 on 2020-10-09 12:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0241_customerservicelog_created_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='product_image_url',
            field=models.CharField(blank=True, max_length=800, null=True),
        ),
    ]
