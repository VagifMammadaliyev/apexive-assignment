from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Min, F, Case, When, Q, BooleanField

from domain.exceptions.logic import NoActiveConfigurationError
from core.models import Configuration as _Configuration
from core.converter import Converter


class Configuration:
    """
    Use this class instead of using Configuration model in core application.
    """

    @property
    def _conf(self) -> _Configuration:
        try:
            return self._loaded_conf
        except AttributeError:
            self._loaded_conf = (
                _Configuration.objects.filter(is_active=True).order_by("id").last()
            )

            if not self._loaded_conf:
                raise NoActiveConfigurationError
            return self._loaded_conf

    def calculate_commission_for_price(self, price, price_currency):
        conf: _Configuration = self._conf

        # Calculate commisson price as usual
        commission_price = (
            conf.order_commission_percentage / Decimal("100.00")
        ) * price

        # Convert it to currency understandable by configuration
        converted_commission_price = Converter.convert(
            commission_price,
            price_currency.code,
            conf.minimum_order_commission_price_currency.code,
        )

        if (
            converted_commission_price < conf.minimum_order_commission_price
        ):  # then return the minimum accepted commission price
            return Converter.convert(
                conf.minimum_order_commission_price,
                conf.minimum_order_commission_price_currency.code,
                price_currency.code,
            )

        return commission_price

    def get_payment_completion_redirect_url(self, payment_service):
        from fulfillment.models import Transaction

        if payment_service == Transaction.CYBERSOURCE_SERVICE:
            return self._conf.cybersource_redirect_url

        elif payment_service == Transaction.PAYPAL_SERVICE:
            return self._conf.paypal_redirect_url

        elif payment_service == Transaction.PAYTR_SERVICE:
            return self._conf.paytr_redirect_url

        return None

    def _format_url(self, url, params=None):
        params = params or {}
        # Remove trailing slash if present
        url = url.rstrip("/")

        # Add url params
        if params:
            query_params = "&".join("%s=%s" % (k, v) for k, v in params.items())
            url += "/?" + query_params

        return url

    def get_activation_email_link(self, uid, token):
        verification_url: str = self._conf.email_verification_url

        if verification_url:
            # Remove tail slash if present
            activation_link = self._format_url(
                verification_url, {"token": token, "uid": uid}
            )

            return activation_link

        raise ValueError("Verifiation URL is not specified in active configuration")

    def get_reset_password_link(self, token):
        reset_password_link: str = self._conf.password_reset_url

        if reset_password_link:
            reset_link = self._format_url(reset_password_link, {"token": token})

            return reset_link

        return ValueError("Reset password URL is not specified in active configuration")

    @property
    def are_notifications_enabled(self):
        return self._conf.notifications_enabled

    @property
    def monthly_spendings_danger_treshold(self):
        return (
            self._conf.monthly_spendings_danger_treshold,
            self._conf.monthly_spendings_treshold_currency,
        )

    @property
    def monthly_spendings_warning_treshold(self):
        return (
            self._conf.monthly_spendings_warning_treshold,
            self._conf.monthly_spendings_treshold_currency,
        )

    @property
    def monthly_spendings_treshold_currency(self):
        return self._conf.monthly_spendings_treshold_currency

    def get_monthly_spendings_status_for_amount(self, amount):
        if amount >= self._conf.monthly_spendings_danger_treshold:
            return {
                "is_warning": False,
                "is_danger": True,
                "message": self._conf.monthly_spendings_danger_message,
            }
        elif amount >= self._conf.monthly_spendings_warning_treshold:
            return {
                "is_warning": True,
                "is_danger": False,
                "message": self._conf.monthly_spendings_warning_message,
            }

        return {
            "is_warning": False,
            "is_danger": False,
            "message": None,
        }

    @property
    def company_name_for_manifest(self):
        company_name = self._conf.manifest_company_name
        return company_name

    @property
    def manifest_report_email(self):
        return self._conf.manifest_reports_sent_to

    @property
    def invite_friend_cashback_percentage(self):
        return self._conf.invited_friend_cashback_percentage

    @property
    def invite_friend_benefit_count(self):
        return self._conf.invited_friend_benefits_count

    def can_get_invite_friend_cashback(self, instance):
        ct = ContentType.objects.get_for_model(instance).pk

        try:
            allowed_cts = self._promo_code_allowed_cts
        except AttributeError:
            allowed_cts = (
                self._conf.invite_friend_discount_appliable_models.all().values_list(
                    "id", flat=True
                )
            )
            self._promo_code_allowed_cts = allowed_cts

        return ct in allowed_cts

    def get_invite_friend_cashback(self):
        from domain.utils.cashback import Cashback

        return Cashback(percentage=self.invite_friend_cashback_percentage)

    def _annotate_shipments_by_arrival_date(self, shipments):
        return shipments.annotate(min_accepted_at=Min("package__real_arrival_date"))

    def annotate_by_exlcude_from_smart_customs(self, shipments):
        start_date = self._conf.smart_customs_start_date
        return self._annotate_shipments_by_arrival_date(shipments).annotate(
            exclude_from_smart_customs=Case(
                When(Q(min_accepted_at__lt=start_date), then=True),
                When(Q(min_accepted_at__gte=start_date), then=False),
                default=None,
                output_field=BooleanField(),
            )
        )

    def filter_customs_commitable_shipments(self, shipments):
        start_date = self._conf.smart_customs_start_date
        return self._annotate_shipments_by_arrival_date(shipments).filter(
            min_accepted_at__gte=start_date
        )

    def filter_customs_non_commitable_shipments(self, shipments):
        start_date = self._conf.smart_customs_start_date
        return self._annotate_shipments_by_arrival_date(shipments).filter(
            min_accepted_at__lt=start_date
        )
