import pytest
from django.urls import reverse

from fulfillment.models import Status


@pytest.mark.django_db
def test_status_inherit_from_shipemnt_when_processing(
    usd, shipment_factory, package_factory, simple_customer, api_client
):
    api_client.force_authenticate(user=simple_customer)

    processing_status = Status.objects.get(
        type=Status.SHIPMENT_TYPE, codename="processing"
    )
    shipment = shipment_factory(user=simple_customer, status=processing_status)

    inforeign_status = Status.objects.get(type=Status.PACKAGE_TYPE, codename="foreign")
    package = package_factory(
        user=simple_customer,
        shipment=shipment,
        status=inforeign_status,
    )

    url = "shipment-retrieve-update-destroy"
    response = api_client.get(reverse(url, args=[shipment.number]))

    data = response.data

    package = data["packages"][0]

    assert package["status"]["display_name"] == inforeign_status.display_name


@pytest.mark.django_db
def test_status_inherit_from_shipemnt_when_ontheway(
    usd, shipment_factory, package_factory, simple_customer, api_client
):
    api_client.force_authenticate(user=simple_customer)

    ontheway_status = Status.objects.get(type=Status.SHIPMENT_TYPE, codename="ontheway")
    shipment = shipment_factory(user=simple_customer, status=ontheway_status)

    inforeign_status = Status.objects.get(type=Status.PACKAGE_TYPE, codename="foreign")
    package = package_factory(
        user=simple_customer,
        shipment=shipment,
        status=inforeign_status,
    )

    url = "shipment-retrieve-update-destroy"
    response = api_client.get(reverse(url, args=[shipment.number]))

    data = response.data

    package = data["packages"][0]

    assert package["status"]["display_name"] == ontheway_status.display_name


@pytest.mark.django_db
def test_status_inherit_from_shipemnt_after_ontheway(
    usd, shipment_factory, package_factory, simple_customer, api_client
):
    api_client.force_authenticate(user=simple_customer)

    other_status = Status.objects.get(
        type=Status.SHIPMENT_TYPE, codename="ontheway"
    ).next  # some other status after ontheway
    shipment = shipment_factory(user=simple_customer, status=other_status)

    inforeign_status = Status.objects.get(type=Status.PACKAGE_TYPE, codename="foreign")
    package = package_factory(
        user=simple_customer,
        shipment=shipment,
        status=inforeign_status,
    )

    url = "shipment-retrieve-update-destroy"
    response = api_client.get(reverse(url, args=[shipment.number]))

    data = response.data

    package = data["packages"][0]

    assert package["status"]["display_name"] == other_status.display_name
