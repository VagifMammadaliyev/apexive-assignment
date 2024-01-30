from itertools import groupby

from django.utils.translation import ugettext_lazy as _

from ontime import messages as msg
from domain.exceptions.base import OnTimeException


class LogicError(OnTimeException):
    error_type = "logic-error"


class DisabledCountryError(LogicError):
    human = msg.DISABLED_COUNTRY_ERROR


class OrderError(LogicError):
    human = msg.ORDER_RELATED_ERROR


class InvalidActionError(LogicError):
    human = msg.THIS_OPERATION_CANNOT_BE_DONE_ERROR

    def __init__(self, *args, order_codes=None, shipment_numbers=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_codes = order_codes
        self.shipment_numbers = shipment_numbers

    def get_extra_info(self):
        if self.order_codes:
            return {"order_codes": self.order_codes}
        if self.shipment_numbers:
            return {"shipment_numbers": self.shipment_numbers}
        return super().get_extra_info()


class DifferentPackageSourceError(LogicError):
    human = msg.PACKAGES_MUST_HAVE_SAME_SOURCE_COUNTRY_ERROR

    def __init__(self, *args, invalid_tracking_code=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.invalid_tracking_codes = invalid_tracking_codes

    def get_extra_info(self):
        if self.invalid_tracking_codes:
            return {"invalid_tracking_codes": self.invalid_tracking_codes}
        return super().get_extra_info()


class AlreadyAcceptedPackageError(LogicError):
    human = msg.ONE_OF_THE_PACKAGES_IS_ALREADY_ACCEPTED_ERROR


class BoxWithUnconfirmedShipmentError(LogicError):
    human = msg.BOX_IS_INVALID_ERROR

    def __init__(self, *args, shipments=[], **kwargs):
        super().__init__(*args, **kwargs)
        self.shipments = shipments

    def get_extra_info(self):
        if self.shipments:
            invalid_boxes = []
            shipments = sorted(self.shipments, key=lambda s: s.box.code)

            for box_code, included_shipments in groupby(
                shipments, key=lambda s: s.box.code
            ):
                invalid_boxes.append(
                    {
                        "code": box_code,
                        "shipments": list(map(lambda s: s.number, included_shipments)),
                    }
                )

            return {"boxes": invalid_boxes}

        return super().get_extra_info()


class QueueError(LogicError):
    error_type = "queue-error"
    human = msg.QUEUE_ERROR


class NoQueueError(QueueError):
    human = msg.NO_QUEUE_IN_WAREHOUSE_ERROR

    def __init__(self, *args, warehouse_codename=None, **kwargs):
        self.warehouse_codename = warehouse_codename

    def get_extra_info(self):
        if self.warehouse_codename:
            return {"warehouse": self.warehouse_codename}

        return super().get_extra_info()


class CourierError(LogicError):
    human = _("Kuryer sifarişində xəta")


class CantPlaceCourierOrderError(CourierError):
    human = _("Kuryer sifarişi yerləşdirilə bilmədi")

    def __init__(self, *args, bad_shipments=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.bad_shipments = bad_shipments or []

    def get_extra_info(self):
        if self.bad_shipments:
            return {
                "shipments": list(map(lambda s: s.number, self.bad_shipments)),
                **super().get_extra_info(),
            }

        return super().get_extra_info()


class ConfigurationError(LogicError):
    error_type = "fatal-error"


class NoActiveConfigurationError(ConfigurationError):
    pass


class ImproperlyConfiguredError(ConfigurationError):
    pass


class ManifestError(LogicError):
    pass


class AcceptedInWrongWarehouseError(LogicError):
    human = msg.WRONG_ACCEPTING_WAREHOUSE_ERROR

    def __init__(self, *args, correct_warehouse=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.correct_warehouse = correct_warehouse

    def get_extra_info(self):
        if self.correct_warehouse:
            from fulfillment.serializers.admin.warehouseman import (
                WarehouseReadSerializer,
            )

            return {
                "correct_warehouse": WarehouseReadSerializer(
                    self.correct_warehouse
                ).data
            }

        return super().get_extra_info()
