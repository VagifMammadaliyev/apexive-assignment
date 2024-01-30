# Generated by Django 3.0 on 2020-08-31 15:10

from django.db import migrations


def add_courier_statuses(apps, schema_editor):
    Status = apps.get_model("fulfillment", "Status")
    status_type = "courier_order_statuses"

    statuses_data = [
        {
            "type": status_type,
            "codename": "created",
            "display_name": "Yaradıldı",
            "order": 100,
        },
        {
            "type": status_type,
            "codename": "ontheway",
            "display_name": "Kuryer yola düşdü",
            "order": 200,
            "extra": {"next": "succeed"},
        },
        {
            "type": status_type,
            "codename": "failed",
            "display_name": "Kuryer təhvil verə bilmədi",
            "order": 300,
            "extra": {"is_final": True},
        },
        {
            "type": status_type,
            "codename": "succeed",
            "display_name": "Kuryer təhvil verdi",
            "order": 400,
            "extra": {"is_final": True},
        },
    ]

    statuses = []
    for status_data in statuses_data:
        statuses.append(Status(**status_data))

    Status.objects.bulk_create(statuses)


def remove_courier_statuses(*args, **kwargs):
    return  # do not do anything


class Migration(migrations.Migration):

    dependencies = [
        ("fulfillment", "0197_auto_20200831_1905"),
    ]

    operations = [
        migrations.RunPython(add_courier_statuses, reverse_code=remove_courier_statuses)
    ]