# Generated by Django 3.0 on 2020-06-09 14:54

from django.db import migrations

from customer.utils import generate_client_code


def populate_client_codes(apps, schema_editor):
    try:
        User = apps.get_model("customer", "User")
    except LookupError:
        return

    for user in User.objects.all():
        user.client_code = generate_client_code(6)
        user.save(update_fields=["client_code"])


def remove_client_codes(apps, schema_editor):
    try:
        User = apps.get_model("customer", "User")
    except LookupError:
        return

    User.objects.all().update(client_code=None)


class Migration(migrations.Migration):

    dependencies = [
        ("customer", "0010_user_client_code"),
    ]

    operations = [
        migrations.RunPython(populate_client_codes, reverse_code=remove_client_codes)
    ]
