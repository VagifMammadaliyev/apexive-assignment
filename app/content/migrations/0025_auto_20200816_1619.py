# Generated by Django 3.0 on 2020-08-16 12:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0024_auto_20200815_1444'),
    ]

    operations = [
        migrations.AlterField(
            model_name='slideritem',
            name='description',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='slideritem',
            name='description_az',
            field=models.TextField(null=True),
        ),
        migrations.AlterField(
            model_name='slideritem',
            name='description_ru',
            field=models.TextField(null=True),
        ),
    ]