# Generated by Django 3.1.2 on 2020-10-26 12:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0256_assignment_deleted_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='description',
            field=models.CharField(blank=True, max_length=400, null=True),
        ),
    ]