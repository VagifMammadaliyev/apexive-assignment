# Generated by Django 3.1.2 on 2020-11-23 21:10

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0270_auto_20201121_0226'),
    ]

    operations = [
        migrations.AddField(
            model_name='package',
            name='warehouseman_description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='PackagePhoto',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.ImageField(upload_to='package/photos/%Y/%m/%d')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('package', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos', related_query_name='photo', to='fulfillment.package')),
            ],
            options={
                'db_table': 'package_photo',
            },
        ),
    ]
