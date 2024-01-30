import pytest
from django.urls import reverse

from fulfillment.models import QueuedItem, Queue


@pytest.mark.django_db
def test_customer_service_reservation(customer_monitor, api_client):
    api_client.force_authenticate(customer_monitor.auth)

    response = api_client.post(reverse("monitor-customer-service-queue-enter"))

    assert response.status_code == 200

    assert QueuedItem.objects.count() == 1, "One queued item must be created"
