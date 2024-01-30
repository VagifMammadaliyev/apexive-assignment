from datetime import datetime

import pytz
from django.utils import timezone
from django.db import models
from django.utils.html import mark_safe


class Currency(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=5, unique=True)
    number = models.CharField(
        max_length=5,
        unique=True,
        null=True,
        blank=True,
        help_text=mark_safe(
            '<a target="blank" href="https://www.iban.com/currency-codes">Full list of currency codes and numbers</a>'
        ),
    )
    symbol = models.CharField(max_length=10)
    rate = models.DecimalField(max_digits=9, decimal_places=4, default=1)

    class Meta:
        db_table = "currency"
        verbose_name_plural = "Currencies"

    def __str__(self):
        return "%s [rate=%s]" % (self.name, self.rate)

    @property
    def is_base(self):
        return self.rate == 1


class CurrencyRateLog(models.Model):
    """
    Rate logs. Each rate log is fetched from central bank every day.
    """

    currency = models.ForeignKey(
        "core.Currency",
        on_delete=models.CASCADE,
        related_name="rate_logs",
        related_query_name="rate_log",
    )
    rate = models.DecimalField(max_digits=9, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "currency_rate_log"

    def __str__(self):
        return "%s [%s]" % (self.rate, self.currency)


def get_map_image(instance, filename):
    return "countries/%s/%s" % (instance.code, filename)


def get_flag_image(instance, filename):
    return "country-flags/%s/%s" % (instance.code, filename)


class Country(models.Model):
    TIMEZONES = list(zip(pytz.all_timezones, pytz.all_timezones))

    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(
        max_length=5,
        unique=True,
        help_text=mark_safe("<b>Alpha-2 code of country. See the link below</b>"),
    )
    number = models.CharField(
        max_length=5,
        unique=True,
        null=True,
        blank=True,
        help_text=mark_safe(
            '<a target="blank" href="https://www.iban.com/country-codes">Full list of country codes and numbers</a>'
        ),
    )

    description = models.TextField(blank=True, null=True)
    flag_image = models.ImageField(upload_to=get_flag_image, null=True, blank=True)
    map_image = models.ImageField(upload_to=get_map_image, null=True, blank=True)
    timezone = models.CharField(max_length=50, choices=TIMEZONES, null=True, blank=True)

    is_base = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    is_default_source = models.BooleanField(default=False)
    is_default_destination = models.BooleanField(default=False)

    is_smart_customs_enabled = models.BooleanField(default=True)
    is_ordering_enabled = models.BooleanField(default=True)
    is_packages_enabled = models.BooleanField(default=True)
    ordering_disabled_message = models.TextField(null=True, blank=True)
    packages_disabled_message = models.TextField(null=True, blank=True)

    currency = models.ForeignKey(
        "core.Currency",
        on_delete=models.CASCADE,
        related_name="countries",
        related_query_name="country",
    )
    phone_code = models.CharField(max_length=10, unique=True)

    display_order = models.IntegerField(default=0)

    class Meta:
        db_table = "country"
        verbose_name_plural = "Countries"

    def __str__(self):
        return "%s [active=%d, base=%d]" % (self.name, self.is_active, self.is_base)

    @property
    def local_datetime(self):
        if self.timezone:
            return datetime.now(tz=pytz.timezone(self.timezone))
        return timezone.localtime(timezone.now())

    @property
    def local_time(self):
        return self.local_datetime.strftime("%H:%M")


class OnlineShoppingDomain(models.Model):
    country = models.ForeignKey(
        "core.Country",
        on_delete=models.CASCADE,
        related_name="shopping_domains",
        related_query_name="shopping_domain",
    )
    domain = models.CharField(max_length=255, help_text="Example: trendyol")

    class Meta:
        db_table = "online_shopping_domain"

    def __str__(self):
        return self.domain


class City(models.Model):
    name = models.CharField(max_length=50, unique=True)
    country = models.ForeignKey("core.Country", on_delete=models.CASCADE)
    code = models.CharField(max_length=10, unique=True, null=True, blank=True)
    is_default_source = models.BooleanField(default=False)
    is_default_destination = models.BooleanField(default=False)

    class Meta:
        db_table = "city"
        verbose_name_plural = "Cities"

    def __str__(self):
        return "%s [%s] [%s]" % (self.name, self.code, self.country.name)


class MobileOperator(models.Model):
    name = models.CharField(max_length=20)
    country = models.ForeignKey(
        "core.Country",
        on_delete=models.CASCADE,
        related_name="mobile_operators",
        related_query_name="mobile_operator",
    )
    prefix = models.CharField(max_length=5)

    class Meta:
        db_table = "mobile_operator"

    def __str__(self):
        return "%s [%s]" % (self.prefix, self.name)

    @property
    def full_prefix(self):
        return self.country.phone_code + self.prefix


class Configuration(models.Model):
    """
    Application configuration. Do not use this model
    directly instead use domain.conf.Configuration
    """

    title = models.CharField(
        max_length=255, help_text="Just a human readable title for your configuration"
    )

    # Order commission related
    order_commission_percentage = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        default=5,
    )
    minimum_order_commission_price = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        default=2,
        help_text=(
            "If commission calculated using percentage is less"
            " than value specified here then use this value instead of calculated."
        ),
    )
    minimum_order_commission_price_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )
    order_commission_info_text = models.TextField(
        null=True,
        blank=True,
        help_text="Text that will be shown to user on order create page",
    )

    paypal_redirect_url = models.URLField(
        null=True, blank=True, help_text="URL to redirect to after payment approval"
    )
    cybersource_redirect_url = models.URLField(
        null=True, blank=True, help_text="URL to redirect to after payment completion"
    )
    paytr_redirect_url = models.URLField(
        null=True, blank=True, help_text="URL to redirect to after payment completion"
    )

    email_verification_url = models.URLField(
        null=True, blank=True, help_text="Front app URL for verifying email address"
    )
    password_reset_url = models.URLField(
        null=True, blank=True, help_text="Front app URL for resetring user password"
    )

    notifications_enabled = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    monthly_spendings_treshold_currency = models.ForeignKey(
        "core.Currency",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    monthly_spendings_danger_treshold = models.DecimalField(
        max_digits=9, decimal_places=2, default=300
    )
    monthly_spendings_warning_treshold = models.DecimalField(
        max_digits=9, decimal_places=2, default=250
    )
    monthly_spendings_warning_message = models.CharField(
        max_length=500, null=True, blank=True
    )
    monthly_spendings_danger_message = models.CharField(
        max_length=500, null=True, blank=True
    )

    manifest_company_name = models.CharField(max_length=255, null=True, blank=True)
    manifest_reports_sent_to = models.EmailField(null=True, blank=True)

    email_address_on_invoice = models.EmailField(null=True, blank=True)
    address_on_invoice = models.TextField(null=True, blank=True)

    # Promo code (invite friend) related fields
    invited_friend_cashback_percentage = models.DecimalField(
        max_digits=9, default=5, decimal_places=2
    )
    invited_friend_benefits_count = models.PositiveIntegerField(
        default=2,
        help_text=(
            "How many transactions must an invited friend complete? "
            "How many transactions will be discounteed for invited "
            "friend and user who invited that friend?"
        ),
    )
    invite_friend_discount_appliable_models = models.ManyToManyField(
        "contenttypes.ContentType",
        limit_choices_to={"model__in": ["shipment", "order", "courierorder"]},
        blank=True,
    )
    common_password_is_enabled = models.BooleanField(default=True)
    common_password_expire_minutes = models.PositiveIntegerField(default=5)

    smart_customs_start_date = models.DateField(null=True, blank=True)
    smart_customs_fail_silently = models.BooleanField(default=False)
    smart_customs_declarations_window_in_days = models.IntegerField(default=15)

    class Meta:
        db_table = "configuration"

    def __str__(self):
        return "Configuration: %s" % (self.title)

    def save(self, *args, **kwargs):
        if not self.pk and self.is_active:
            Configuration.objects.all().update(is_active=False)
        elif self.pk and self.is_active:
            Configuration.objects.exclude(pk=self.pk).update(is_active=False)
        return super().save(*args, **kwargs)
