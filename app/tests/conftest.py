from datetime import datetime

import pytest
from pytest_factoryboy import register
from django.core.management import call_command
from django.contrib.contenttypes.models import ContentType

from customer.models import User, Role
from core.models import Configuration, Currency
from fulfillment.models import Monitor, Shipment
from customer.models import Balance
from tests import factories
from domain.conf import Configuration as AppConf

# Factory fixtures
register(factories.UserFactory)
register(factories.OrderFactory)
register(factories.CountryFactory)
register(factories.CurrencyFactory)
register(factories.ProductCategoryFactory)
register(factories.WarehouseFactory)
register(factories.ProductTypeFactory)
register(factories.ConfigurationFactory)
register(factories.PackageFactory)
register(factories.ShipmentFactory)
register(factories.ShopFactory)
register(factories.OrderedProductFactory)
register(factories.TransactionFactory)
register(factories.TariffFactory)
register(factories.CityFactory)
register(factories.PromoCodeFactory)


# Loading main fixture (statuses, user roles etc.)
@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        try:
            call_command("loaddata", "fixtures/core_data.json")
        except:
            pass


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def staff_user(db):
    user = User.objects.create_staff_user(
        full_phone_number="+9949990000", email="staff@ontime.az", password="123"
    )
    return user


@pytest.fixture
def simple_customer(db):
    user = User.objects.create_user(
        full_phone_number="+994516576432", email="email@gmail.com", password="123"
    )
    balance = Balance.objects.create(
        user=user, currency=factories.CurrencyFactory(code="USD"), amount=0
    )
    return user


@pytest.fixture
def rich_customer(db):
    user = User.objects.create_user(
        full_phone_number="+994550000001", email="rich@royal.com", password="123"
    )
    balance = Balance.objects.create(
        user=user, currency=factories.CurrencyFactory(code="USD"), amount=10000
    )
    return user


@pytest.fixture(autouse=True)
def dummy_conf(db):
    # create dummy conf
    conf: Configuration = factories.ConfigurationFactory(
        minimum_order_commission_price=0,
        order_commission_percentage=0,
        notifications_enabled=False,
        smart_customs_start_date=datetime(2021, 1, 1),
    )
    conf.invite_friend_discount_appliable_models.add(
        ContentType.objects.get_for_model(Shipment)
    )
    currency = factories.CurrencyFactory(code="USD")
    conf = AppConf()
    return conf


@pytest.fixture
def usd(db, currency_factory):
    return currency_factory(code="USD")


@pytest.fixture
def customer_monitor(db):
    user = User.objects.create_staff_user(full_phone_number="cmtr", password="123")
    user.role = Role.objects.get(type=Role.MONITOR)
    user.save()
    monitor = Monitor.objects.create(
        auth=user,
        code="CMTR1",
        type=Monitor.FOR_CUSTOMER,
        warehouse=factories.WarehouseFactory(),
    )
    return monitor
