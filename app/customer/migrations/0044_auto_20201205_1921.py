# Generated by Django 3.1.2 on 2020-12-05 15:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0043_auto_20201202_2304'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='email',
            field=models.EmailField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.AddConstraint(
            model_name='user',
            constraint=models.UniqueConstraint(condition=models.Q(is_active=True), fields=('email',), name='unique_email_when_is_active'),
        ),
    ]
