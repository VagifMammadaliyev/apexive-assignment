import time
from typing import Iterable, List, Dict, Any, Optional
import datetime

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet
from django.utils.functional import cached_property
from django.utils import timezone
from django.contrib.admin.models import LogEntry, ContentType, CHANGE
from sentry_sdk import capture_exception

from core.models import Country
from fulfillment.models import (
    Shipment,
    Status,
    CustomsProductType,
    NotificationEvent as EVENTS,
)
from domain.conf import Configuration
from domain.exceptions.smart_customs import (
    InvalidApiResponseError,
    NoAirwayBillError,
    NoRegNumberError,
    SmartCustomsError,
)


ONTIME_PROXY_URL = settings.ONTIME_PROXY_URL
ONTIME_PROXY_TOKEN = settings.ONTIME_PROXY_TOKEN


class EXCEPTION_CODE:
    SUCCESS = "200"
    ALREADY_ADDED = "015"
    OPERATION_ALREADY_DONE = "048"


def get_country_number_by_code(code):
    c = Country.objects.filter(code=code).values("number").first()
    if c:
        return c["number"]
    return None


class CustomsClient(object):
    """Client for integration with Customs API"""

    DIRECTION = 1
    AZ_NUMERIC = "031"

    def __init__(self):
        # check if statuses present
        self._in_foreign_status

    @cached_property
    def _in_foreign_status(self):
        return Status.objects.get(type=Status.PACKAGE_TYPE, codename="foreign")

    def _check_if_prepared(self, shipment, prepared_packages):
        for prepared_package in prepared_packages:
            if shipment.number == prepared_package["trackinG_NO"]:
                return True
        return False

    def prepare_packages(self, shipments: Iterable[Shipment]) -> List[Dict[str, Any]]:
        """Prepare packages to be submitted to customs api"""
        packages_data = []
        for shipment in shipments:
            if shipment.total_weight and not shipment.fixed_total_weight:
                shipment.fixed_total_weight = shipment.total_weight
            if not shipment.total_price and shipment.fixed_total_weight:
                (
                    shipment.total_price,
                    shipment.total_price_currency,
                ) = shipment.calculate_total_price()
                shipment.declared_price = shipment.calculate_declared_price()
            packages_data.append(
                {
                    "direction": self.DIRECTION,
                    "trackinG_NO": shipment.number,
                    "transP_COSTS": float(str(shipment.discounted_total_price)),
                    "quantitY_OF_GOODS": shipment.products_quantity,
                    "weighT_GOODS": float(str(shipment.custom_total_weight)),
                    "invoyS_PRICE": float(str(shipment.declared_price)),
                    "currencY_TYPE": shipment.declared_price_currency.number,
                    "fin": shipment.recipient.id_pin,
                    "idxaL_NAME": shipment.recipient.full_name,
                    "idxaL_ADRESS": shipment.recipient.address,
                    "phone": shipment.recipient.get_phone_number_for_customs(),
                    "ixraC_NAME": shipment.get_seller(),
                    "ixraC_ADRESS": shipment.get_sender_address(),
                    "goodS_TRAFFIC_FR": shipment.source_warehouse.country.number,
                    "goodS_TRAFFIC_TO": shipment.destination_warehouse.country.number,
                    "goodsList": shipment.get_goods(),
                }
            )
        return packages_data

    def _get_headers(self):
        return {"ApiKey": settings.CUSTOMS_API_TOKEN}

    def make_request(self, accept_status_codes=None, **kwargs):
        if not accept_status_codes:
            accept_status_codes = [200]
        response = requests.post(
            ONTIME_PROXY_URL + "/proxy",
            headers={"x-api-token": ONTIME_PROXY_TOKEN},
            json=kwargs,
        )
        status, headers, body = self._handle_response(response)
        if status not in accept_status_codes:
            if isinstance(body, dict):
                exception = body.get("exception", {})
                err_message = exception.get("errorMessage", "")
            else:
                exception = body
                err_message = body
            if not Configuration()._conf.smart_customs_fail_silently:
                raise InvalidApiResponseError(str(body))
        return status, headers, body

    def _handle_response(self, original_response):
        if original_response.status_code != 200:
            raise Exception(
                "Ontime proxy server failed (%s): %s"
                % (original_response.status_code, original_response.json())
            )

        _original_response = original_response.json()
        return (
            _original_response["status"],
            _original_response["headers"],
            _original_response["body"],
        )

    def _update_shipments(self, shipments, **update_data):
        if isinstance(shipments, QuerySet):
            # update efficiently
            shipments.update(**update_data)
        else:
            # update using less efficient query
            Shipment.objects.filter(id__in=[s.id for s in shipments]).update(
                **update_data
            )

    def _get_url(self, path):
        return settings.CUSTOMS_API_BASE_URL + path

    def _filter_commitable(self, shipments):
        return list(
            filter(
                lambda s: s.source_warehouse.country.is_smart_customs_enabled, shipments
            )
        )

    def _get_intervals_from_date_range(self, *args, **kwargs):
        from domain.utils import get_intervals_from_date_range

        return get_intervals_from_date_range(*args, **kwargs)

    def _group_items(self, *args, **kwargs):
        from domain.utils import group_items

        return group_items(*args, **kwargs)

    def _get_exception_code(self, body):
        exception_data = body.get("exception", {})
        return exception_data.get("code", None)

    def _check_if_already_committed(self, exception_code):
        return exception_code == EXCEPTION_CODE.ALREADY_ADDED

    def _filter_already_committed(self, body, shipments):
        tracking_codes = body.get("data")
        return [shipment for shipment in shipments if shipment.number in tracking_codes]

    def _check_if_committed(self, shipment, error_data):
        if not error_data:
            return False
        error_code = error_data.get(shipment.number)
        if error_code == "200":
            return True
        return error_code == "015"

    def commit_packages(self, shipments: Iterable[Shipment], notify=True):
        shipments = self._filter_commitable(shipments)

        for shipment_group in self._group_items(shipments, 90):
            prepared_packages = self.prepare_packages(shipments=shipment_group)
            status, headers, body = self.make_request(
                accept_status_codes=[200, 400],
                headers=self._get_headers(),
                body=prepared_packages,
                method="post",
                url=self._get_url("/api/v2/carriers"),
            )

            to_be_updated = []
            if status == 200:
                to_be_updated = [
                    s
                    for s in shipment_group
                    if self._check_if_prepared(s, prepared_packages)
                ]
            elif status == 400:
                exception_data = body.get("exception", {}).get("validationError", {})
                to_be_updated = [
                    s
                    for s in shipment_group
                    if self._check_if_committed(s, exception_data)
                ]
            elif status == 422:
                to_be_updated = []

            self._update_shipments(
                to_be_updated,
                is_declared_to_customs=True,
                updated_at=timezone.now(),
                declared_to_customs_at=timezone.now(),
            )
            if notify:
                from domain.services import create_notification

                for s in to_be_updated:
                    create_notification(s, EVENTS.ON_COMMIT_TO_CUSTOMS, [s.user])

        return body.get("data", None)

    def delete_tracking_code(self, tracking_code: str):
        status, headers, body = self.make_request(
            headers=self._get_headers(),
            method="delete",
            url=self._get_url(f"/api/v2/carriers/{tracking_code}"),
        )
        return body.get("data", None)

    def delete_package(self, shipment: Shipment, deleting_admin_id=None):
        tracking_code = shipment.number
        self.delete_tracking_code(tracking_code=tracking_code)
        # reset all data related to customs
        shipment.is_declared_to_customs = False
        shipment.declared_to_customs_at = None
        shipment.is_depeshed = False
        shipment.is_deleted_from_smart_customs = False
        shipment.is_deleted_from_smart_customs_by_us = True
        shipment.is_added_to_box = False
        shipment.customs_payment_status_id = None
        shipment.customs_payment_status_description = None
        shipment.customs_goods_list_data = None
        shipment.declared_items_title = shipment.generate_declared_items_title()
        shipment._must_recalculate = True
        shipment._accepted = True
        shipment._skip_commiting = True
        shipment.save()
        # log if deleting_admin_id is provided
        if deleting_admin_id:
            LogEntry.objects.log_action(
                user_id=deleting_admin_id,
                content_type_id=ContentType.objects.get_for_model(Shipment).id,
                object_id=shipment.id,
                object_repr=str(shipment),
                action_flag=CHANGE,
                change_message="Deleted from customs db. Reset all fields related to customs",
            )

    def fetch_product_types(self) -> List[Dict[str, Any]]:
        status, headers, body = self.make_request(
            headers=self._get_headers(),
            method="get",
            url=self._get_url("/api/v2/carriers/goodsgroupslist"),
        )
        response = requests.get(
            ONTIME_PROXY_URL,
        )
        return body.get("data", [])

    @transaction.atomic
    def get_or_create_product(
        self,
        fetched_product: Dict[str, Any],
        parent_fetched_product: Optional[Dict[str, Any]] = None,
    ):
        fetched_name_az = (
            fetched_product.get("goodsNameAz")
            or fetched_product.get("goodsNameEn")
            or fetched_product.get("goodsNameRu")
        )  # fallback langs: AZ->EN->RU
        fetched_name_ru = fetched_product.get("goodsNameRu")
        fetched_name_en = fetched_product.get("goodsNameEn")
        fetched_is_deleted = fetched_product.get("isDeleted")
        # try to get already saved product type, it not exists create it
        try:
            customs_ptype = CustomsProductType.objects.get(
                original_id=fetched_product.get("id")
            )
            # check if some fields updated
            must_update = False
            if (
                customs_ptype.name_az != fetched_name_az
                or customs_ptype.name_en != fetched_name_en
                or customs_ptype.name_ru != fetched_name_ru
                or customs_ptype.is_deleted != fetched_is_deleted
            ):
                must_update = True
            # update both fields (we are saving anyway... not so bad on performance)
            if must_update:
                customs_ptype.name_az = fetched_name_az
                customs_ptype.name_en = fetched_name_en
                customs_ptype.name_ru = fetched_name_ru
                customs_ptype.is_deleted = fetched_is_deleted
                customs_ptype.save(
                    update_fields=[
                        "is_deleted",
                        "name_az",
                        "name_ru",
                        "name_en",
                        "updated_at",
                    ]
                )
        except CustomsProductType.DoesNotExist:
            # create
            customs_ptype = CustomsProductType.objects.create(
                original_id=fetched_product.get("id"),
                name_az=fetched_name_az,
                name_ru=fetched_name_ru,
                name_en=fetched_name_en,
                is_deleted=fetched_is_deleted,
            )
        # check for parent
        if parent_fetched_product:
            # get / create that parent
            parent_customs_ptype = self.get_or_create_product(parent_fetched_product)
            customs_ptype.parent = parent_customs_ptype
            customs_ptype.save(update_fields=["parent"])
        else:
            # remove parent from this product type
            customs_ptype.parent = None
            customs_ptype.save(update_fields=["parent"])

        return customs_ptype

    @transaction.atomic
    def get_or_create_products(self, fetched_products: List[Dict[str, Any]]):
        products = fetched_products
        already_checked_ids = set()
        for product in products:
            if product.get("id") in already_checked_ids:
                continue  # skip already checked product
            already_checked_ids.add(product.get("id"))
            # search for parent if necessary
            parent_id = product.get("parentId")
            parent = None
            if parent_id:
                for _product in products:
                    if _product.get("id") == parent_id:
                        parent = _product
                # add parent id to checked ids
                # because it will be created anyway
                already_checked_ids.add(parent_id)
            self.get_or_create_product(product, parent)

    def update_product_types(self):
        p_types = self.fetch_product_types()
        self.get_or_create_products(p_types)

    def _format_time(self, datetime_obj: Optional[datetime.datetime]):
        if datetime_obj:
            return datetime_obj.strftime("%Y-%m-%dT%H:%M:%SZ")
        return None

    def get_declared_packages(
        self,
        date_from: datetime.datetime,
        date_to: datetime.datetime,
        tracking_code: str = None,
    ):
        data = []
        for start_date, end_date in self._get_intervals_from_date_range(
            date_from, date_to, interval=datetime.timedelta(days=3)
        ):
            offset, limit = 0, 50
            has_data = True
            fdate_from = self._format_time(start_date)
            fdate_to = self._format_time(end_date)
            print(f"====Checking from {fdate_from} to {fdate_to}====")
            while has_data:
                try:
                    print(f"---Limit {limit}, offset {offset}---")
                    body = {}
                    if tracking_code:
                        body["trackingNumber"] = tracking_code
                    else:
                        body = {"dateFrom": fdate_from, "dateTo": fdate_to}
                    status, headers, body = self.make_request(
                        headers=self._get_headers(),
                        method="post",
                        body=body,
                        url=self._get_url(
                            f"/api/v2/carriers/declarations/{offset}/{limit}"
                        ),
                    )
                    has_data = not self._check_if_data_empty(body)
                    offset += limit
                    time.sleep(5)
                except InvalidApiResponseError as err:
                    self._handle_exception(err)
                if body.get("data", None):
                    if tracking_code:
                        has_data = False  # break the loop
                    yield from body["data"]
                has_data = False
            if tracking_code:
                break

    def _check_if_data_empty(self, body):
        data = body.get("data", [])
        return not bool(data)

    def _update_user_declared_packages(self, declared_packages: List[Dict[Any, Any]]):
        """Updates packages declared by user to smart customs."""
        declared_packages_map = {}
        for declared_package in declared_packages:
            tracking_code = declared_package.get("trackingNumber")
            pay_status_id = declared_package.get("payStatus_Id")
            pay_status_desc = declared_package.get("payStatus")
            reg_number = declared_package.get("regNumber")
            goods_list = declared_package.get("goodsList", [])
            _data = {
                "reg_number": reg_number,
                "pay_status_id": pay_status_id,
                "pay_status_desc": pay_status_desc,
                "goods_list": goods_list,
            }
            declared_packages_map[tracking_code] = _data

        bad_declarations = []
        for shipment in Shipment.objects.filter(
            number__in=list(declared_packages_map.keys())
        ):
            _data = declared_packages_map[shipment.number]
            reg_number = _data.get("reg_number")
            pay_status_id = _data.get("pay_status_id")
            pay_status_desc = _data.get("pay_status_desc")
            goods_list = _data.get("goods_list")
            if reg_number:
                shipment.customs_goods_list_data = {"goodsList": goods_list}
                shipment.reg_number = reg_number
                shipment.customs_payment_status_id = pay_status_id
                shipment.customs_payment_status_description = pay_status_desc
                shipment.is_declared_by_user = True
                # this will set declared items title to one provided by customs
                shipment.declared_items_title = shipment.generate_declared_items_title()
                shipment.declared_price = shipment.calculate_declared_price()
                shipment._must_recalculate = True
                shipment._accepted = True
                shipment.save()
            else:
                bad_declarations.append(shipment.number)

        if bad_declarations:
            exc = Exception(
                "Did not get reg_number value for following tracking_codes: %s"
                % bad_declarations
            )
            self._handle_exception(exc)

    def _update_user_deleted_packages(self, deleted_reg_numbers: List[str]) -> int:
        """
        Check for deleted declarations by user from smart customs app and
        mark them as deleted. Returns count of those declarations.
        """
        return Shipment.objects.filter(reg_number__in=deleted_reg_numbers).update(
            is_deleted_from_smart_customs=True,
        )

    def refresh_packages_states_from_smart_customs(self):
        self.check_declared_packages_from_smart_customs()
        self.check_deleted_packages_from_smart_customs()

    def check_declared_packages_from_smart_customs(self):
        conf = Configuration()
        try:
            print("Checking declared")
            in_foreign_decs = Shipment.objects.filter(
                is_declared_to_customs=True,
                is_declared_by_user=False,
                declared_to_customs_at__isnull=False,
                is_added_to_box=False,
            ).values("declared_to_customs_at")
            if conf._conf.smart_customs_declarations_window_in_days > 0:
                print("Using window days for determining interval")
                from_date = timezone.localtime(timezone.now()) - datetime.timedelta(
                    days=conf._conf.smart_customs_declarations_window_in_days
                )
                to_date = timezone.localtime(timezone.now()) + datetime.timedelta(
                    days=1
                )
            else:
                print("Finding earliest and latest declarations")
                earliest_dec = in_foreign_decs.earliest("declared_to_customs_at")
                latest_dec = in_foreign_decs.latest("declared_to_customs_at")
                backup = datetime.timedelta(hours=3)
                from_date = (
                    timezone.localtime(earliest_dec["declared_to_customs_at"]) - backup
                )
                to_date = (
                    timezone.localtime(latest_dec["declared_to_customs_at"]) + backup
                )
            declared_packages = self.get_declared_packages(from_date, to_date)
            self._update_user_declared_packages(declared_packages)
        except Shipment.DoesNotExist:
            pass

    def check_deleted_packages_from_smart_customs(self):
        conf = Configuration()
        try:
            print("Checking deleted")
            user_declared_packages = Shipment.objects.filter(
                is_deleted_from_smart_customs=False, is_added_to_box=True
            ).values("declared_to_customs_at")
            if conf._conf.smart_customs_declarations_window_in_days > 0:
                print("Using window days for determining interval")
                from_date = timezone.localtime(timezone.now()) - datetime.timedelta(
                    days=conf._conf.smart_customs_declarations_window_in_days
                )
                to_date = timezone.localtime(timezone.now()) + datetime.timedelta(
                    days=1
                )
            else:
                print("Finding earliest and latest declarations")
                earliest_dec = user_declared_packages.earliest("declared_to_customs_at")
                latest_dec = user_declared_packages.latest("declared_to_customs_at")
                from_date = timezone.localtime(earliest_dec["declared_to_customs_at"])
                to_date = timezone.localtime(latest_dec["declared_to_customs_at"])
            deleted_reg_numbers = self.get_deleted_packages_reg_numbers(
                from_date, to_date
            )
            self._update_user_deleted_packages(deleted_reg_numbers)
        except Shipment.DoesNotExist:
            pass

    def _handle_exception(self, exc):
        if settings.PROD:
            capture_exception(exc)
        else:
            raise exc

    def get_deleted_packages_reg_numbers(
        self,
        date_from: datetime.datetime,
        date_to: datetime.datetime,
        tracking_code: str = None,
    ):
        reg_numbers = []
        for start_date, end_date in self._get_intervals_from_date_range(
            date_from,
            date_to,
            interval=datetime.timedelta(days=3),
        ):
            offset, limit = 0, 50
            has_data = True
            fdate_from = self._format_time(start_date)
            fdate_to = self._format_time(end_date)
            rbody = {}
            if tracking_code:
                rbody["trackingNumber"] = tracking_code
            else:
                rbody = {"dateFrom": fdate_from, "dateTo": fdate_to}
            while has_data:
                try:
                    status, headers, body = self.make_request(
                        headers=self._get_headers(),
                        method="post",
                        body=rbody,
                        url=self._get_url(
                            f"/api/v2/carriers/deleteddeclarations/{offset}/{limit}"
                        ),
                    )
                    has_data = not self._check_if_data_empty(body)
                    offset += limit
                    time.sleep(5)
                except InvalidApiResponseError as err:
                    self._handle_exception(err)
                    continue
                if body.get("data"):
                    reg_numbers += [entry["REGNUMBER"] for entry in body["data"]]
                else:
                    reg_numbers = []
            if tracking_code:
                break
        return reg_numbers

    def _is_from_values(self, declarations):
        """
        Checks if declarations is actually a result
        of calling `.values(...)` on queryset.
        """
        if declarations:  # naive approach
            # check if declarations are the result of calling
            # `.values(...)` on queryset
            _declaration = declarations[0]
            return isinstance(_declaration, dict)
        return False  # we don't know...

    def _check_if_already_depeshed(self, body, shipment):
        return self._check_if_already_added_to_box(body, shipment)

    def depesh_packages(self, shipments):
        from domain.utils import group_items

        # contruct data to be posted
        for shipment_group in group_items(
            shipments, group_size=50, remove_none_items=True
        ):
            data = []
            collected_packages = []
            for shipment in filter(lambda s: not s.is_depeshed, shipment_group):
                tracking_code = shipment.number
                airway_bill = shipment.box.transportation.airwaybill
                reg_num = shipment.reg_number
                box_number = shipment.box_id and shipment.box.code or "ONTIMEBOX"
                # must have reg number and already obtainer airwaybill from airport
                if not reg_num:
                    continue
                if not airway_bill:
                    continue
                data.append(
                    {
                        "trackingNumber": tracking_code,
                        "airWaybill": airway_bill,
                        "regNumber": reg_num,
                        "depeshNumber": box_number,
                    }
                )
                collected_packages.append(shipment)

            status, headers, body = self.make_request(
                accept_status_codes=[200, 400],
                headers=self._get_headers(),
                url=self._get_url(
                    "/api/v2/carriers/depesh",
                ),
                method="post",
                body=data,
            )
            if status == 200:
                to_be_updated = collected_packages
            else:
                to_be_updated = [
                    s
                    for s in collected_packages
                    if self._check_if_already_depeshed(body, s)
                ]
            self._update_shipments(to_be_updated, is_depeshed=True)

    def _check_if_already_added_to_box(self, body, shipment):
        exception_data = body.get("data", {})
        tracking_code = shipment.number
        exception_code = exception_data.get(tracking_code, None)
        return exception_code and exception_code in (
            EXCEPTION_CODE.OPERATION_ALREADY_DONE,
            EXCEPTION_CODE.SUCCESS,
        )

    def add_to_boxes(self, shipments):
        from domain.utils import group_items

        data = []
        for shipment_group in group_items(shipments, 90):
            to_be_added = []
            for shipment in shipment_group:
                reg_number = shipment.reg_number
                tracking_code = shipment.number
                # must have reg number
                if not reg_number:
                    print("%s does not have reg number" % tracking_code)
                    continue
                data.append({"regNumber": reg_number, "trackingNumber": tracking_code})
                to_be_added.append(shipment)

            status, headers, body = self.make_request(
                accept_status_codes=[200, 400],
                headers=self._get_headers(),
                url=self._get_url("/api/v2/carriers/addtoboxes"),
                method="post",
                body=data,
            )
            if status == 200:
                to_be_updated = to_be_added
            else:
                to_be_updated = [
                    s
                    for s in to_be_added
                    if self._check_if_already_added_to_box(body, s)
                ]

            self._update_shipments(
                to_be_updated, is_added_to_box=True, updated_at=timezone.now()
            )


def filter_addable_shipments(shipments):
    return shipments.filter(
        is_declared_by_user=True,
        reg_number__isnull=False,
        is_deleted_from_smart_customs=False,
    )
