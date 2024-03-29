# Generated by Django 3.0 on 2020-06-09 15:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0002_faq'),
    ]

    operations = [
        migrations.AddField(
            model_name='announcement',
            name='slug',
            field=models.SlugField(max_length=100, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='announcement',
            name='slug_az',
            field=models.SlugField(max_length=100, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='announcement',
            name='slug_ru',
            field=models.SlugField(max_length=100, null=True, unique=True),
        ),
    ]
