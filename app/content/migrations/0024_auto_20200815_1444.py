# Generated by Django 3.0 on 2020-08-15 10:44

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0023_auto_20200815_1437'),
    ]

    operations = [
        migrations.AlterField(
            model_name='footercolumn',
            name='display_order',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name='FooterElement',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100)),
                ('title_az', models.CharField(max_length=100, null=True)),
                ('title_ru', models.CharField(max_length=100, null=True)),
                ('raw_link', models.URLField(blank=True, null=True)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('column', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='elements', related_query_name='element', to='content.FooterColumn')),
                ('flat_page', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='content.FlatPage')),
            ],
            options={
                'db_table': 'footer_element',
            },
        ),
    ]