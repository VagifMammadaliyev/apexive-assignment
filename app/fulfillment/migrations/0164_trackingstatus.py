# Generated by Django 3.0 on 2020-08-19 15:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0163_auto_20200815_2100'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrackingStatus',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pl_number', models.CharField(max_length=5, unique=True)),
                ('problem_code', models.CharField(blank=True, max_length=3, null=True, unique=True)),
                ('problem_code_description', models.TextField(blank=True, null=True)),
                ('problem_code_description_az', models.TextField(blank=True, null=True)),
                ('problem_code_description_ru', models.TextField(blank=True, null=True)),
                ('tracking_code', models.CharField(max_length=4, unique=True)),
                ('tracking_code_description', models.TextField(blank=True, null=True)),
                ('tracking_code_description_az', models.TextField(blank=True, null=True)),
                ('tracking_code_description_ru', models.TextField(blank=True, null=True)),
                ('tracking_code_explanation', models.TextField(blank=True, null=True)),
                ('tracking_code_explanation_az', models.TextField(blank=True, null=True)),
                ('tracking_code_explanation_ru', models.TextField(blank=True, null=True)),
                ('tracking_condition_code', models.CharField(blank=True, max_length=4, null=True, unique=True)),
                ('tracking_condition_code_description', models.TextField(blank=True, null=True)),
                ('tracking_condition_code_description_az', models.TextField(blank=True, null=True)),
                ('tracking_condition_code_description_ru', models.TextField(blank=True, null=True)),
                ('mandatory_comment', models.TextField(blank=True, null=True)),
                ('mandatory_comment_az', models.TextField(blank=True, null=True)),
                ('mandatory_comment_ru', models.TextField(blank=True, null=True)),
                ('final_status', models.BooleanField(default=False)),
                ('delivery_status', models.BooleanField(default=False)),
            ],
            options={
                'db_table': 'tracking_status',
            },
        ),
    ]
