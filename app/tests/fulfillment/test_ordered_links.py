import pytest
from django.urls import reverse
from django.utils import timezone

from fulfillment.models import OrderedProduct, Package
from fulfillment.tasks import save_ordered_products_in_shipment

ordered_products_url_name = "ordered-product-slider"


@pytest.mark.django_db
def test_ordered_products_slider_with_no_visible_products(
    api_client, ordered_product_factory
):
    ordered_product_factory.create_batch(5, is_visible=False)

    url = reverse(ordered_products_url_name)
    response = api_client.get(url)

    assert response.data["count"] == 0, "No ordered products mustbe visible"


@pytest.mark.django_db
def test_ordered_products_slider_with_visible_products(
    api_client, ordered_product_factory
):
    ordered_product_factory.create_batch(5, is_visible=True)

    url = reverse(ordered_products_url_name)
    response = api_client.get(url)

    assert response.data["count"] == 5, "Visible ordered products are not exposed"


@pytest.mark.django_db
def test_saving_ordered_products_from_shipment(
    dummy_conf,
    simple_customer,
    currency_factory,
    shipment_factory,
    order_factory,
    package_factory,
):
    assert OrderedProduct.objects.count() == 0, "Ordered product created out of nowhere"

    packages = []

    for i in range(2):
        package = package_factory(
            user=simple_customer,
            order=order_factory(
                user=simple_customer,
            ),
        )
        packages.append(package)

    shipment = shipment_factory(
        user=simple_customer,
        total_price=5,
        total_price_currency=currency_factory(code="USD"),
    )

    Package.objects.all().update(shipment_id=shipment.id)

    save_ordered_products_in_shipment([shipment.id])

    assert OrderedProduct.objects.count() == 2, "2 ordered products must be created"
