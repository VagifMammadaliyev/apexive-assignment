from django.db import models
from django.utils.translation import ugettext_lazy as _

from ontime import messages as msg


class AdditionalService(models.Model):
    PACKAGE_TYPE = "for_packages"
    SHIPMENT_TYPE = "for_shipments"

    TYPES = (
        (PACKAGE_TYPE, msg.PACKAGE_TYPE),
        (SHIPMENT_TYPE, msg.SHIPMENT_TYPE),
    )

    type = models.CharField(choices=TYPES, max_length=15)
    title = models.CharField(max_length=512)
    description = models.TextField()

    # Wheter this service need additonal attachment from staff person
    needs_attachment = models.BooleanField(default=False)
    # Wheter additional note should be supplied by user
    needs_note = models.BooleanField(default=False)

    price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    price_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )

    # Some warehouse may not be able to provide such service.
    # And each country (for now) has only one warehouse, so
    # when user is selecting additonal services we must check by related warehouse!
    warehouses = models.ManyToManyField(
        "fulfillment.Warehouse",
        related_name="services",
        related_query_name="service",
        through="WarehouseAdditionalService",
    )

    packages = models.ManyToManyField(
        "fulfillment.Package",
        through="PackageAdditionalService",
        related_name="services",
        related_query_name="service",
    )
    shipments = models.ManyToManyField(
        "fulfillment.Shipment",
        through="ShipmentAdditionalService",
        related_name="services",
        related_query_name="service",
    )

    class Meta:
        db_table = "additional_service"

    def __str__(self):
        return "%s [%s %s attachment=%s]" % (
            self.title,
            self.price,
            self.price_currency,
            self.needs_attachment,
        )


def get_shipment_service_attachment_path(instance, filename):
    return "cargo/shipments/%s/services/%s/%s" % (
        instance.ordered_service.shipment.number,
        instance.ordered_service.service.title,
        filename,
    )


def get_package_service_attachment_path(instance, filename):
    return "cargo/packages/%s/services/%s/%s" % (
        instance.ordered_service.package.id,
        instance.ordered_service.service.title,
        filename,
    )


class ShipmentAdditionalService(models.Model):
    shipment = models.ForeignKey(
        "fulfillment.Shipment",
        on_delete=models.CASCADE,
        related_name="ordered_services",
        related_query_name="ordered_service",
    )
    service = models.ForeignKey(
        "fulfillment.AdditionalService", on_delete=models.CASCADE
    )
    note = models.TextField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        db_table = "shipment_service"

    def __str__(self):
        return "%s - %s" % (self.shipment, self.service)


class PackageAdditionalService(models.Model):
    package = models.ForeignKey(
        "fulfillment.Package",
        on_delete=models.CASCADE,
        related_name="ordered_services",
        related_query_name="ordered_service",
    )
    service = models.ForeignKey(
        "fulfillment.AdditionalService", on_delete=models.CASCADE
    )
    note = models.TextField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        db_table = "package_service"

    def __str__(self):
        return "%s - %s" % (self.package, self.service)


class PackageAdditionalServiceAttachment(models.Model):
    ordered_service = models.ForeignKey(
        "fulfillment.PackageAdditionalService",
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(
        null=True, blank=True, upload_to=get_package_service_attachment_path
    )

    class Meta:
        db_table = "package_service_attachment"

    def __str__(self):
        return "Attachment [%s]" % self.ordered_service


class ShipmentAdditionalServiceAttachment(models.Model):
    ordered_service = models.ForeignKey(
        "fulfillment.ShipmentAdditionalService",
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(
        null=True, blank=True, upload_to=get_shipment_service_attachment_path
    )

    class Meta:
        db_table = "shipment_service_attachment"

    def __str__(self):
        return "Attachment [%s]" % self.ordered_service


class WarehouseAdditionalService(models.Model):
    warehouse = models.ForeignKey(
        "fulfillment.Warehouse",
        on_delete=models.CASCADE,
        related_name="allowed_services",
        related_query_name="allowed_service",
    )
    service = models.ForeignKey(
        "fulfillment.AdditionalService",
        on_delete=models.CASCADE,
        related_name="serving_warehouses",
        related_query_name="serving_warehouse",
    )

    class Meta:
        db_table = "warehouse_servoce"

    def __str__(self):
        return "[%s] - [%s]" % (self.warehouse.title, self.service.title)
