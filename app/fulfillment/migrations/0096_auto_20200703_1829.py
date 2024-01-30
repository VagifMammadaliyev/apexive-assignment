# Generated by Django 3.0 on 2020-07-03 14:29

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fulfillment', '0095_auto_20200703_0031'),
    ]

    operations = [
        migrations.CreateModel(
            name='Transportation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('air', 'Hava ilə')], default='air', max_length=10)),
                ('departure_time', models.DateTimeField(blank=True, null=True)),
                ('arrival_time', models.DateTimeField(blank=True, null=True)),
                ('destination_warehouse', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='accepted_flights', related_query_name='accepted_flight', to='fulfillment.Warehouse')),
                ('source_warehouse', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='departure_flights', related_query_name='departure_flight', to='fulfillment.Warehouse')),
            ],
            options={
                'db_table': 'transportation',
            },
        ),
        migrations.AlterField(
            model_name='box',
            name='flight',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='boxes', related_query_name='box', to='fulfillment.Transportation'),
        ),
        migrations.DeleteModel(
            name='Transport',
        ),
    ]