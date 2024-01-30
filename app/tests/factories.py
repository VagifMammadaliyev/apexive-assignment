import string
import random
import datetime

import factory
import factory.fuzzy
from faker import Factory as FakerFactory
from faker import Faker

from core.models import Country, Currency, Configuration, City
from customer.models import User, Role
from fulfillment.models import (
    Order,
    ProductCategory,
    ProductType,
    Package,
    Status,
    Shipment,
    Warehouse,
    OrderedProduct,
    Shop,
    Transaction,
    Tariff,
    PromoCode,
)

faker = Faker()
faker_factory = FakerFactory.create()


def generate_random_azerbaijani_number():
    operators = ["51", "55", "77", "99", "50", "70"]
    body = "".join(random.choice(string.digits) for _ in range(7))
    return f"+994{random.choice(operators)}{body}"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    full_phone_number = factory.fuzzy.FuzzyAttribute(
        fuzzer=generate_random_azerbaijani_number
    )
    email = factory.fuzzy.FuzzyAttribute(fuzzer=faker.email)
    first_name = factory.fuzzy.FuzzyAttribute(fuzzer=faker.first_name)
    last_name = factory.fuzzy.FuzzyAttribute(fuzzer=faker.last_name)
    birth_date = factory.fuzzy.FuzzyAttribute(fuzzer=faker.date_object)
    is_active = True
    is_staff = False
    is_superuser = False
    date_joined = factory.fuzzy.FuzzyAttribute(fuzzer=faker.date_between)
    role = factory.Iterator(Role.objects.filter(type=Role.USER))
    password = factory.PostGenerationMethodCall("set_password", "secret")


def generate_currency_rate(instance, *args, **kwargs):
    if instance.code == "USD":
        return 1

    if not instance.rate:
        return random.randint(0, 100) / 100 + 0.1

    return instance.rate


class CurrencyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Currency
        django_get_or_create = ("code", "number")

    # name = factory.Iterator(["US Dollar", "Turkish Lira", "Azerbaijan manat"])
    # code = factory.Iterator(["USD", "TRY", "AZN"])
    # number = factory.Iterator(["840", "949", "944"])
    # symbol = factory.Iterator(["$", "₺", "₼"])
    # rate = factory.Iterator([1, 0.58, 0.12])
    name = factory.fuzzy.FuzzyAttribute(fuzzer=faker.currency_name)
    code = factory.fuzzy.FuzzyAttribute(fuzzer=faker.currency_code)
    symbol = factory.fuzzy.FuzzyAttribute(fuzzer=faker.currency_symbol)
    number = factory.fuzzy.FuzzyAttribute(
        fuzzer=lambda: "".join(random.choice(string.digits) for _ in range(5))
    )
    rate = factory.PostGeneration(generate_currency_rate)


class CountryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Country
        django_get_or_create = ("code",)

    currency = factory.SubFactory(CurrencyFactory)

    name = factory.Iterator(["United states", "Turkey", "Azerbaijan"])
    code = factory.Iterator(["US", "TR", "AZ"])
    is_base = factory.Iterator([False, False, True])
    is_active = factory.Iterator([True, True, False])
    phone_code = factory.Iterator(["+1", "+90", "+994"])


class CityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = City

    name = factory.fuzzy.FuzzyAttribute(fuzzer=faker.city)
    country = factory.SubFactory(CountryFactory)
    code = factory.fuzzy.FuzzyAttribute(fuzzer=faker.postcode)


class WarehouseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Warehouse

    city = factory.SubFactory(CityFactory)
    country = factory.SelfAttribute("city.country")
    address = factory.fuzzy.FuzzyAttribute(fuzzer=faker.address)


class ProductCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductCategory


class ProductTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductType

    category = factory.SubFactory(ProductCategoryFactory)


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order
        django_get_or_create = ("order_code",)

    source_country = factory.SubFactory(CountryFactory)
    status = factory.Iterator(Status.objects.filter(type=Status.ORDER_TYPE))
    product_category = factory.SubFactory(ProductCategoryFactory)
    product_type = factory.SubFactory(ProductTypeFactory)
    order_code = factory.fuzzy.FuzzyText(
        length=8, chars=string.ascii_letters + string.digits
    )

    product_price_currency = factory.SelfAttribute("source_country.currency")
    cargo_price_currency = factory.SelfAttribute("source_country.currency")
    commission_price_currency = factory.SelfAttribute("source_country.currency")
    total_price_currency = factory.SelfAttribute("source_country.currency")
    remainder_price_currency = factory.SelfAttribute("source_country.currency")
    product_description = factory.fuzzy.FuzzyText()
    description = factory.fuzzy.FuzzyText()
    product_url = factory.fuzzy.FuzzyAttribute(fuzzer=faker.uri)
    product_image_url = factory.fuzzy.FuzzyAttribute(fuzzer=faker.image_url)


class ConfigurationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Configuration

    minimum_order_commission_price_currency = factory.SubFactory(CurrencyFactory)
    monthly_spendings_treshold_currency = factory.SubFactory(CurrencyFactory)


class ShipmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Shipment
        django_get_or_create = ("number",)

    status = factory.Iterator(Status.objects.filter(type=Status.SHIPMENT_TYPE))
    number = factory.fuzzy.FuzzyText(
        length=8, chars=string.ascii_letters + string.digits
    )
    source_country = factory.SubFactory(CountryFactory)
    source_warehouse = factory.SubFactory(WarehouseFactory)
    current_warehouse = factory.SubFactory(WarehouseFactory)
    destination_warehouse = factory.SubFactory(WarehouseFactory)
    is_serviced = True


class PackageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Package
        django_get_or_create = ("user_tracking_code",)

    user_tracking_code = factory.fuzzy.FuzzyText(
        length=8, chars=string.ascii_letters + string.digits
    )
    arrival_date = factory.fuzzy.FuzzyDate(
        start_date=datetime.date.today(),
        end_date=datetime.date.today() + datetime.timedelta(days=10),
    )
    status = factory.Iterator(Status.objects.filter(type=Status.PACKAGE_TYPE))
    source_country = factory.SubFactory(CountryFactory)


class ShopFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Shop


class OrderedProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrderedProduct

    category = factory.SubFactory(ProductCategoryFactory)
    country = factory.SubFactory(CountryFactory)
    price_currency = factory.SelfAttribute("country.currency")
    shipping_price_currency = factory.SelfAttribute("country.currency")
    shop = factory.SubFactory(ShopFactory)


class TransactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Transaction

    currency = factory.SubFactory(CurrencyFactory)
    amount = factory.fuzzy.FuzzyDecimal(low=0, high=1000, precision=2)
    purpose = Transaction.BALANCE_INCREASE
    type = Transaction.CASH
    completed = True
    original_amount = factory.SelfAttribute("amount")
    original_currency = factory.SelfAttribute("currency")
    completed_at = factory.fuzzy.FuzzyAttribute(fuzzer=faker.date_time_this_month)


class TariffFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tariff

    title = "From 0kg to 10kg"

    source_city = factory.SubFactory(CityFactory)
    destination_city = factory.SubFactory(CityFactory)
    price = 10
    discounted_price = 10
    price_currency = factory.SubFactory(CurrencyFactory)

    min_weight = 0
    max_weight = 10


class PromoCodeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PromoCode

    user = factory.SubFactory(UserFactory)
