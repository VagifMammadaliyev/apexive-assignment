import string
import random
from decimal import Decimal

from django.db import models, transaction
from django.db.models import Sum, Prefetch
from django.conf import settings
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.fields import GenericRelation

from ontime import messages as msg
from fulfillment.enums.status_codenames import SCN
from fulfillment.models.abc import ArchivableModel, SoftDeletionModel
from fulfillment.models import Tariff, Status, Transaction, StatusEvent
from fulfillment.models.abc import (
    ArchivableModel,
    SoftDeletionModel,
    DiscountableModelMixin,
    CashbackableModelMixin,
)
from fulfillment.models.ticket import TicketMixin
from core.converter import Converter
from core.models import Currency


class Shipment(
    SoftDeletionModel,
    ArchivableModel,
    TicketMixin,
    DiscountableModelMixin,
    CashbackableModelMixin,
):
    notifications = GenericRelation(
        "fulfillment.Notification",
        content_type_field="object_type",
        object_id_field="object_id",
    )
    transactions = GenericRelation(
        "fulfillment.Transaction",
        content_type_field="object_type",
        object_id_field="object_id",
    )
    discounts = GenericRelation(
        "fulfillment.Discount",
        content_type_field="object_type",
        object_id_field="object_id",
    )
    promo_codes = GenericRelation(
        "fulfillment.PromoCodeBenefit",
        content_type_field="object_type",
        object_id_field="object_id",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shipments",
        related_query_name="shipment",
    )
    status = models.ForeignKey(
        "fulfillment.Status",
        on_delete=models.PROTECT,
        related_name="related_shipments",
        related_query_name="related_shipment",
        limit_choices_to={"type": Status.SHIPMENT_TYPE},
    )
    tracking_status = models.ForeignKey(
        "fulfillment.TrackingStatus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="related_shipments",
        related_query_name="related_shipment",
    )
    number = models.CharField(max_length=30, unique=True, db_index=True)
    source_country = models.ForeignKey(
        "core.Country",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    current_warehouse = models.ForeignKey(
        "fulfillment.Warehouse",
        on_delete=models.PROTECT,
        related_name="current_shipments",
        related_query_name="current_shipment",
        null=True,
        blank=True,
    )
    # Local warehouse for related user
    source_warehouse = models.ForeignKey(
        "fulfillment.Warehouse",
        on_delete=models.PROTECT,
        related_name="foreign_shipments",
        related_query_name="foreign_shipment",
        null=True,
        blank=True,
    )
    destination_warehouse = models.ForeignKey(
        "fulfillment.Warehouse",
        on_delete=models.PROTECT,
        related_name="local_shipments",
        related_query_name="local_shipment",
    )
    # destination_user_address = models.ForeignKey(
    #     "customer.Address", on_delete=models.SET_NULL, blank=True, null=True
    # )
    recipient = models.ForeignKey(
        "customer.FrozenRecipient",
        on_delete=models.SET_NULL,
        related_name="shipments",
        related_query_name="shipment",
        null=True,
        blank=True,
    )

    user_note = models.TextField(null=True, blank=True)
    staff_note = models.TextField(null=True, blank=True)

    # Used for calculating montly spendings of related user
    is_volume_considered = models.BooleanField(default=False)
    fixed_total_weight = models.DecimalField(max_digits=9, decimal_places=3, default=0)
    fixed_height = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    fixed_width = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    fixed_length = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    confirmed_properties = models.BooleanField(default=False)
    declared_items_title = models.TextField(null=True, blank=True)
    declared_price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    declared_price_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )

    # payment_method = models.CharField(max_length=10, choices=Transaction.TYPES)
    total_price = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True
    )
    total_price_currency = models.ForeignKey(
        "core.Currency",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )

    shelf = models.CharField(max_length=255, null=True, blank=True)

    # Used for checking if this shipment must be accounted for montly spendings of related user
    declared_at = models.DateTimeField(null=True, blank=True)
    is_dangerous = models.BooleanField(default=False)
    contains_batteries = models.BooleanField(default=False)
    is_oneclick = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=False)

    box = models.ForeignKey(
        "fulfillment.Box",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipments",
        related_query_name="shipment",
    )

    queued_item = models.ForeignKey(
        "fulfillment.QueuedItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipments",
        related_query_name="shipment",
    )
    # Field used by warehouseman in a queue to check
    # shipment (marks it as found for example).
    is_checked_by_warehouseman = models.BooleanField(default=False)

    courier_order = models.ForeignKey(
        "fulfillment.CourierOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipments",
        related_query_name="shipment",
    )

    is_serviced = models.BooleanField(default=False)  # fulfilled ordered services

    status_last_update_time = models.DateTimeField(
        null=True, blank=True, default=timezone.now
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    extra = models.JSONField(default=dict, blank=True)
    expenses = models.JSONField(null=True, blank=True)

    # customs related fields
    is_depeshed = models.BooleanField(
        default=False
    )  # notified customs about completed package
    is_added_to_box = models.BooleanField(
        default=False
    )  # added to boxes using customs API
    is_declared_to_customs = models.BooleanField(
        default=False, db_index=True
    )  # notified customs about package arrived to foreign warehouse
    declared_to_customs_at = models.DateTimeField(null=True, blank=True, db_index=True)
    is_deleted_from_smart_customs = models.BooleanField(
        default=False, db_index=True
    )  # user deleted this declaration using smart customs app
    is_deleted_from_smart_customs_by_us = models.BooleanField(
        default=False, db_index=True
    )
    is_declared_by_user = models.BooleanField(
        default=False, db_index=True
    )  # declared by user using smart customs application
    reg_number = models.CharField(
        null=True, blank=True, db_index=True, max_length=40
    )  # registration number obtained from customs api
    customs_payment_status_id = models.IntegerField(
        db_index=True, null=True, blank=True
    )
    customs_payment_status_description = models.TextField(null=True, blank=True)
    # invoice price data provided by customer in smart
    # customs application, do not use this field directly
    # instead use `customs_product_price`, `customs_product_price_currency`
    # and `customs_product_quantity`, `customs_product_price_preview`
    customs_goods_list_data = models.JSONField(default=dict, null=True, blank=True)

    class Meta:
        db_table = "shipment"

    def __str__(self):
        return "%s [%s]" % (self.number, self.status_id and self.status.codename)

    @property
    def identifier(self):
        return self.number

    @property
    def can_be_payed_by_user(self):
        return (
            bool(self.total_price_currency_id and self.total_price)
            and self.status.codename
            in ["tobeshipped", "customs", "ontheway", "received"]
            and not self.is_paid
        )

    @property
    def can_user_view_bill(self):
        return bool(self.total_price and self.total_price_currency_id)

    @property
    def can_be_edited_by_user(self):
        return False

    @property
    def can_be_deleted_by_user(self):
        if self.deleted_at:  # already deleted
            return False

        if self.packages.filter(current_warehouse__isnull=False).exists():
            return False

        return self.status.codename in [
            "processing",
            "tobeshipped",
            "ontheway",
            "customs",
        ]

    @property
    def courier_can_be_ordered(self):
        return bool(
            self.status.codename not in ["deleted", "done"]
            and not self.courier_order_id
            and self.total_price
            and self.total_price_currency_id
            and self.confirmed_properties
        )
        # return (
        #     not self.courier_order_id
        #     and self.status_id
        #     and self.status.codename == "received"
        # )

    @property
    def can_be_confirmed_by_warehouseman(self):
        has_weight = bool(self.fixed_total_weight)
        is_volume_considered = self.is_volume_considered
        has_properties = all([self.fixed_height, self.fixed_length, self.fixed_width])
        properties_are_validated = has_properties if is_volume_considered else True
        return (
            # not self.confirmed_properties
            has_weight
            and properties_are_validated
            and self.check_serviced()
        )

    @property
    def can_be_marked_as_serviced(self):
        return not self.check_serviced()

    @property
    def can_be_updated_by_warehouseman(self):
        return not self.confirmed_properties

    @property
    def can_be_placed_in_a_box(self):
        # return (
        #     self.confirmed_properties
        #     and self.check_serviced()
        #     and self.total_price
        #     and self.total_price_currency_id
        # )
        return True

    # @property
    # def source_country_id(self):
    #     any_package = self.packages.first()
    #     return any_package and any_package.source_country_id

    @property
    def dimensions(self):
        from domain.utils import ShipmentDimensions

        if self.is_volume_considered:
            return ShipmentDimensions(
                self.fixed_height, self.fixed_width, self.fixed_length
            )

        return None

    @property
    def consolidate(self):
        return not self.is_oneclick

    @property
    def can_user_archive(self):
        return self.status.codename in [SCN.SHIPMENT.DONE, SCN.SHIPMENT.DELETED]

    @property
    def _customs_goods_list(self):
        _data = self.customs_goods_list_data or {}
        data = _data.get("goodsList", [])
        return data

    @property
    def customs_product_price(self) -> Decimal:
        goods_list = self._customs_goods_list
        product_price = Decimal("0")
        shipping_price_subtracted = False
        for product in goods_list:
            invoice_price = product.get("invoicePriceUsd")
            invoice_price = invoice_price.replace("$", "").strip()
            if invoice_price:
                invoice_price = Decimal(str(invoice_price))
                if not shipping_price_subtracted:
                    # first item of goodslist comes with shipping price
                    # added, subtract it for correct invoice price
                    if self.total_price:
                        invoice_price -= self.total_price
                        shipping_price_subtracted = True
                product_price += Decimal(invoice_price)
        return round(product_price, 2)

    @property
    def customs_product_price_currency(self) -> Currency:
        return Currency.objects.get(code="USD")

    @property
    def customs_product_price_currency_id(self) -> int:
        return Currency.objects.filter(code="USD").values("id").first()["id"]

    @property
    def customs_declared_items(self) -> str:
        goods_list = self._customs_goods_list
        declared_items = []
        for product in goods_list:
            product_desc = product.get("goodsName")
            if product_desc:
                declared_items.append(product_desc)
        if declared_items:
            return " / ".join(declared_items)
        return

    @property
    def customs_product_quantity(self) -> int:
        goods_list = self._customs_goods_list
        total_qty = 0
        for product in goods_list:
            qty = product.get("quantity", 1)
            total_qty += qty
        return int(total_qty)

    @property
    def has_customs_product_price(self) -> bool:
        return bool(self._customs_goods_list)

    @property
    def customs_product_price_preview(self) -> str:
        return Exchange(
            self.customs_product_price, self.customs_product_price_currency
        ).get_with_sign()

    def check_serviced(self):
        """
        Check if shipment itself and related packages are serviced.
        """
        return (
            all(self.packages.values_list("is_serviced", flat=True))
            and self.is_serviced
        )

    @transaction.atomic
    def save(self, *args, source_country_code=None, **kwargs):
        from domain.services import (
            try_create_promo_code_cashbacks,
            update_or_create_transaction_for_shipment,
        )

        if not self.number or getattr(self, "_regen_number", False):
            self.number = self._generate_new_shipment_number(source_country_code)

        if not self.status_id:
            self.status = Status.objects.get(
                codename="processing", type=Status.SHIPMENT_TYPE
            )

        if not self.declared_price_currency_id:
            self.declared_price_currency = Currency.objects.get(code="USD")

        must_recalculate = getattr(self, "_must_recalculate", False)

        if (
            must_recalculate
            or not self.total_price_currency_id
            or (self.confirmed_properties and not self.total_price)
        ):
            # self.total_price_currency = self.destination_warehouse.city.country.currency
            self.total_price, self.total_price_currency = self.calculate_total_price()
            if (
                self.total_price
                and self.total_price_currency
                and getattr(self, "_update_declared_price", False)
            ):
                self.declared_price = self.calculate_declared_price()
            if (
                self.total_price
                and self.total_price_currency
                and not getattr(self, "_accepted", False)
            ):
                update_or_create_transaction_for_shipment(self)

        creating = not bool(self.pk)
        super().save(*args, **kwargs)

        if creating:
            try_create_promo_code_cashbacks(self)

        if self.can_be_committed_to_customs:
            self.commit_to_customs()

        skip_box_adding = getattr(self, "_skip_box_adding", False)
        if self.box_id and not self.is_added_to_box:
            from fulfillment.tasks import add_to_customs_box

            transaction.on_commit(lambda: add_to_customs_box.delay([self.pk]))

    def commit_to_customs(self):
        from fulfillment.tasks import commit_to_customs

        transaction.on_commit(lambda: commit_to_customs.delay([self.pk]))

    @property
    def can_be_committed_to_customs(self):
        return (
            not self.is_declared_to_customs
            and not self.is_deleted_from_smart_customs
            and self.recipient_id
            and self.source_warehouse_id
            and self.destination_warehouse_id
            and self.total_weight
            and self.packages.exists()
            and self.status_id
            and self.status.codename in ["tobeshipped", "processing", "problematic"]
            and not getattr(self, "_skip_commiting", False)
        )

    def generate_declared_items_title(self):
        if self.has_customs_product_price:  # then it has items description too
            return self.customs_declared_items

        titles = []

        for package in self.packages.all():
            for product in package.products.all():
                titles.append(product.normalized_description)

        return ", ".join(titles)

    def get_matching_tariff(self) -> Tariff:
        """
        Used as helping method to create invoice.
        """
        if self.total_price_currency_id and self.source_warehouse_id:
            from domain.utils import TariffCalculator

            calculator = TariffCalculator()
            price, tariff = calculator.calculate(self)

            if tariff:
                return tariff

            # return Tariff.objects.get_for_weight(
            #     self.total_weight,
            #     self.source_warehouse.city_id,
            #     self.destination_warehouse.city_id,
            #     is_dangerous=self.is_dangerous,
            # )

        return None

    def calculate_total_price(self):
        # if not (self.total_price_currency_id or self.source_country_id):
        #     return None

        from domain.utils import TariffCalculator

        calculator = TariffCalculator()
        price, tariff = calculator.calculate(self)

        if tariff:
            currency = tariff.price_currency
            total_price = Decimal("0.00")
            total_price = price

            # Calculate additional services price
            # First get service prices for this shipment
            service_prices = self.ordered_services.values_list(
                "service__price", "service__price_currency__code"
            )

            # Calculate
            for price, currency_code in service_prices:
                total_price += Converter.convert(price, currency_code, currency.code)

            # Then get service prices for related packages
            packages = self.packages.prefetch_related(
                Prefetch("ordered_services", to_attr="prefetched_services")
            )

            # Calculate. FIXME: May be there is a better way! O(n^2)!
            for package in packages:
                for ordered_service in package.prefetched_services:
                    total_price += Converter.convert(
                        ordered_service.service.price,
                        ordered_service.service.price_currency.code,
                        currency.code,
                    )

            return total_price, currency

        return None, None

    def calculate_declared_price(self):
        total_price = Decimal("0.00")

        if not self.has_customs_product_price:
            for (
                product_price,
                product_qty,
                product_cargo_price,
                product_cargo_price_currency,
                product_com_price,
                product_com_price_currency,
                product_price_currency,
            ) in self.packages.values_list(
                "product__price",
                "product__quantity",
                "product__cargo_price",
                "product__cargo_price_currency__code",
                "product__commission_price",
                "product__commission_price_currency__code",
                "product__price_currency__code",
            ):
                total_price += (
                    Converter.convert(
                        product_price * product_qty,
                        product_price_currency,
                        self.declared_price_currency.code,
                    )
                    + Converter.convert(
                        product_cargo_price,
                        product_cargo_price_currency or product_price_currency,
                        self.declared_price_currency.code,
                    )
                    + Converter.convert(
                        product_com_price,
                        product_com_price_currency or product_price_currency,
                        self.declared_price_currency.code,
                    )
                )
        else:
            total_price = self.customs_product_price

        delivery_price = Decimal("0")

        # We can't calculate delivery price at some point of time
        # so we just wait for the right time.
        # It is too important to call this method when declared_at is set.
        if self.total_price_currency_id and self.total_price:
            delivery_price = Converter.convert(
                self.total_price,
                self.total_price_currency.code,
                self.declared_price_currency.code,
            )

        return total_price + delivery_price

    @property
    def total_weight(self):
        if self.fixed_total_weight:
            return self.fixed_total_weight

        try:
            return self._total_weight
        except AttributeError:
            _total_weight = self.packages.filter(weight__isnull=False).aggregate(
                total_weight=Sum("weight")
            )["total_weight"]

            if _total_weight:
                self._total_weight = Decimal(_total_weight)
                return self._total_weight

            return Decimal("0")

    @property
    def volume_weight(self):
        if self.fixed_height and self.fixed_width and self.fixed_length:
            return (self.fixed_height * self.fixed_width * self.fixed_length) / Decimal(
                "6000"
            )
        return Decimal("0")

    @property
    def custom_total_weight(self):
        """
        Calculates volume weight first, then compares to actual weight.
        Takes the biggest value and uses it to get the tariff.
        """
        if self.is_volume_considered:
            return max(self.volume_weight, self.total_weight)

        return self.total_weight

    @property
    def chargable_volume_weight(self):
        if self.fixed_height and self.fixed_width and self.fixed_length:
            return (self.fixed_height * self.fixed_width * self.fixed_length) / Decimal(
                "6000.00"
            )

        return self.total_weight

    def _generate_new_shipment_number(
        self, source_country_code=None, company_code="ON"
    ):
        """
        Returns tracking code of type:
            USXXYZZZRRRRAZ
        Meaning:
            US - Source country code
            XX - Company code, default ON (Ontime)
            Y - Packages count, only the last digit!
            ZZZ - Declared price without decimal part
            RRR - Randomly generated digits
            AZ - Destination country code
        """
        _radnom_string = lambda n: "".join(
            random.choice(string.digits) for _ in range(n)
        )

        # Get one of the packages
        country_code_part = source_country_code
        any_package = self.packages.first()
        if not country_code_part:
            country_code_part = (
                self.source_warehouse.city.country.code
                if self.source_warehouse_id
                else any_package
                and any_package.source_country.code
                or _radnom_string(2)
            )

        prefix = country_code_part
        suffix = self.destination_warehouse.city.country.code
        packages_count = (
            str(self.packages.count())[-1] if any_package else _radnom_string(1)
        )
        declared_price = (
            str(round(self.declared_price))
            if self.declared_price
            else _radnom_string(3)
        )
        random_part = _radnom_string(4)

        number = "{source_country}{company_code}{packages_count}{declared_price}{random_part}{dest_country}".format(
            source_country=prefix,
            company_code=company_code,
            packages_count=packages_count,
            declared_price=declared_price,
            random_part=random_part,
            dest_country=suffix,
        )

        if Shipment.objects.filter(number=number).exists():
            return self._generate_new_shipment_number(source_country_code)

        return number

    @property
    def products_quantity(self):
        total_qty = 0
        for package in self.packages.annotate(qty=Sum("product__quantity")).values(
            "qty"
        ):
            total_qty += package.get("qty", 0) or 0
        return total_qty

    def get_seller(self):
        to_be_concatted = []
        for seller, country in self.packages.all().values_list(
            "seller", "source_country__name"
        ):
            if seller:
                to_be_concatted.append(seller)
            elif country:
                to_be_concatted.append(country)
        return ", ".join(to_be_concatted)

    def get_sender_address(self):
        to_be_concatted = list(
            (seller_address or package_country_en or package_country_fallback)
            for (
                seller_address,
                package_country_en,
                package_country_fallback,
            ) in self.packages.values_list(
                "seller_address",
                "source_country__name_en",
                "source_country__name",
            )
        )
        return ", ".join(to_be_concatted)

    def get_goods(self):
        goods = []
        for package in self.packages.all():
            for product in package.products.all():
                goods.append(
                    {"goodS_ID": 0, "namE_OF_GOODS": product.normalized_description}
                )

        return goods

    def serialize_for_payment(self):
        return {
            "identifier": self.identifier,
            "type": "shipment",
            "title": self.user_note or msg.SHIPMENT_WORD,
            "weight": self.total_weight,
            "is_oneclick": self.is_oneclick,
        }

    def serialize_for_notification(self):
        return {
            "identifier": self.identifier,
            "type": "shipment",
            "title": self.user_note or self.number,
            "object": None,
        }

    def serialize_for_ticket(self, for_admin=False):
        data = {
            "identifier": self.identifier,
            "type": "shipment",
            "title": "%s (%s)"
            % (
                self.identifier,
                msg.SHIPMENT_WORD,
                # self.get_has_ticket_message(prefix=" "),
            ),
        }

        if not for_admin:
            data["has_ticket"] = self.get_has_ticket()

        return data

    def post_soft_delete(self):
        self.packages.all().update(shipment=None)
        self.courier_order = None
        self.save(update_fields=["courier_order"])

    def post_user_delete(self):
        at_least_one_with_current_warehouse = self.packages.filter(
            current_warehouse__isnull=False
        ).exists()
        if not at_least_one_with_current_warehouse:
            for package in self.packages.all():
                package.delete()

    @classmethod
    def post_soft_queryset_delete(cls, qs):
        from fulfillment.models import Package

        qs.update(courier_order=None)
        Package.objects.filter(shipment__id__in=qs.values("id")).update(shipment=None)

    def _get_related_transactions(self):
        return self.transactions.filter(
            is_deleted=False,
            purpose=Transaction.SHIPMENT_PAYMENT,
            deleted_at__isnull=True,
        )

    @cached_property
    def has_related_transaction(self):
        return self._get_related_transactions().exists()

    @cached_property
    def related_transaction(self):
        return self._get_related_transactions().first()


class Box(models.Model):
    box_number = models.CharField(max_length=50, blank=True, null=True)
    transportation = models.ForeignKey(
        "fulfillment.Transportation",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="boxes",
        related_query_name="box",
    )
    code = models.CharField(max_length=255, null=True, blank=True)
    source_warehouse = models.ForeignKey(
        "fulfillment.Warehouse",
        on_delete=models.PROTECT,
        related_name="boxes",
        related_query_name="box",
    )
    destination_warehouse = models.ForeignKey(
        "fulfillment.Warehouse",
        on_delete=models.PROTECT,
        related_name="arrived_boxes",
        related_query_name="arrived_box",
        null=True,
        blank=True,
    )
    total_weight = models.DecimalField(decimal_places=3, max_digits=9, default=0)

    height = models.DecimalField(decimal_places=2, max_digits=9, default=0)
    width = models.DecimalField(decimal_places=2, max_digits=9, default=0)
    length = models.DecimalField(decimal_places=2, max_digits=9, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expenses = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "box"
        verbose_name_plural = "Boxes"

    def __str__(self):
        return self.code

    @transaction.atomic
    def save(self, *args, **kwargs):
        must_generate_code = getattr(self, "must_generate_code", True)
        super().save(*args, **kwargs)
        self.refresh_from_db(fields=["id"])

        if self.id and self.destination_warehouse_id and must_generate_code:
            self.code = "%s-%s-%s-%d" % (
                self.source_warehouse.city.code,
                self.destination_warehouse.country.code
                if self.destination_warehouse.is_universal
                else self.destination_warehouse.city.code,
                self.destination_warehouse.codename,
                self.id,
            )
            self.must_generate_code = False  # prevent recursion
            self.save(update_fields=["code"])

        return self


class Transportation(models.Model):
    AIR = "air"

    TYPES = ((AIR, msg.BY_AIR),)

    number = models.CharField(
        max_length=255, null=True, blank=True
    )  # DBX-BAK-01-01-2020
    type = models.CharField(max_length=10, choices=TYPES, default=AIR)

    # Where source airport is located
    source_city = models.ForeignKey(
        "core.City",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departured_transports",
        related_query_name="departured_transport",
    )
    # Where destination airport is located
    destination_city = models.ForeignKey(
        "core.City",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="arrived_transports",
        related_query_name="arrived_transport",
    )
    departure_time = models.DateTimeField(null=True, blank=True)
    arrival_time = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    # If this transportation is made by Aramex (for liquid items)
    is_ar = models.BooleanField(default=False)

    xml_manifest = models.FileField(
        upload_to="xml-manifests/%Y/%m/%d/", null=True, blank=True
    )
    xml_manifest_last_export_time = models.DateTimeField(null=True, blank=True)
    manifest = models.FileField(upload_to="manifests/%Y/%m/%d/", null=True, blank=True)
    manifest_last_export_time = models.DateTimeField(null=True, blank=True)

    ordering_starts_at = models.PositiveIntegerField(default=1)
    expenses = models.JSONField(null=True, blank=True)

    airwaybill = models.CharField(max_length=99, null=True, blank=True)
    airway = models.ForeignKey(
        "fulfillment.Airway",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transportations",
        related_query_name="transportation",
    )

    class Meta:
        db_table = "transportation"

    def __str__(self):
        return self.number or "-- NO NUMBER --"


def get_shipment_receiver_signature_path(instance, filename):
    return "shipments/%s/receiver-info/signature/%s/%s/%s/%s_%s" % (
        instance.shipment.number,
        instance.first_name,
        instance.last_name,
        instance.id_pin,
        timezone.now().timestamp(),
        filename,
    )


class ShipmentReceiver(models.Model):
    shipment = models.OneToOneField(
        "fulfillment.Shipment", on_delete=models.CASCADE, related_name="receiver"
    )
    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    id_pin = models.CharField(max_length=7, null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    signature = models.ImageField(upload_to=get_shipment_receiver_signature_path)
    is_real_owner = models.BooleanField(default=True)

    class Meta:
        db_table = "shipment_receiver"

    def __str__(self):
        return "Shipment %s receiver [%s %s %s]" % (
            self.shipment.number,
            self.first_name,
            self.last_name,
            self.phone_number,
        )
