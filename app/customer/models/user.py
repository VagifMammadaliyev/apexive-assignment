import secrets
import string
from datetime import timedelta

from django.db import transaction
from django.utils import translation
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.html import mark_safe
from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from ontime import messages as msg
from domain.exceptions.customer import EmailConfirmationError, AlreadyVerifiedError
from customer.tokens import account_activation_token
from customer.tasks import send_sms_with_random_code, send_verification_email
from core.models import Country


class Role(models.Model):
    USER = "user"
    ADMIN = "admin"
    CASHIER = "cashier"
    WAREHOUSEMAN = "warehouseman"
    SHOPPING_ASSISTANT = "shopping_assistant"
    CONTENT_MANAGER = "content_manager"
    MONITOR = "monitor"
    CUSTOMER_SERVICE = "customer_service"
    COURIER = "courier"
    CUSTOMS_AGENT = "customs_agent"

    TYPES = (
        (USER, msg.USER_ROLE),
        (ADMIN, msg.ADMIN_ROLE),
        (CASHIER, msg.CASHIER_ROLE),
        (WAREHOUSEMAN, msg.WAREHOUSEMAN_ROLE),
        (SHOPPING_ASSISTANT, msg.SHOPPING_ASSISTANT_ROLE),
        (CONTENT_MANAGER, msg.CONTENT_MANAGER_ROLE),
        (CUSTOMER_SERVICE, msg.CUSTOMER_SERVICE_ROLE),
        (MONITOR, msg.MONITOR_ROLE),
        (COURIER, msg.COURIER_ROLE),
        (CUSTOMS_AGENT, msg.CUSTOMS_AGENT_ROLE),
    )

    FLAT_TYPES = [t[0] for t in TYPES]
    ANIMATE_TYPES = [
        USER,
        ADMIN,
        CASHIER,
        WAREHOUSEMAN,
        SHOPPING_ASSISTANT,
        CONTENT_MANAGER,
        CUSTOMER_SERVICE,
        COURIER,
        CUSTOMS_AGENT,
    ]
    INANIMATE_TYPES = [MONITOR]

    type = models.CharField(max_length=20, unique=True, choices=TYPES)

    class Meta:
        db_table = "role"

    def __str__(self):
        return self.get_type_display()


class UserManager(BaseUserManager):
    def create_user(self, full_phone_number, email=None, password=None, commit=True):
        if not full_phone_number:
            raise ValueError(_("Phone number cannot be blank"))

        user = self.model(
            full_phone_number=full_phone_number,
            email=self.normalize_email(email) if email else None,
        )
        user.set_password(password)

        user.role = Role.objects.get(type=Role.USER)

        if commit:
            user.save(using=self._db)

        return user

    def create_staff_user(
        self, full_phone_number, email=None, password=None, commit=True
    ):
        user = self.create_user(full_phone_number, email, password, commit=False)
        user.is_staff = True
        user.is_active = True

        if commit:
            user.save(using=self._db)

        return user

    def create_superuser(
        self, full_phone_number, email=None, password=None, commit=True
    ):
        user = self.create_staff_user(full_phone_number, email, password, commit=False)
        user.is_superuser = True
        user.role = Role.objects.get(type=Role.ADMIN)

        if commit:
            user.save(using=self._db)

        return user


class User(AbstractBaseUser, PermissionsMixin):
    client_code = models.CharField(max_length=20, unique=True, db_index=True)
    full_phone_number = models.CharField(max_length=15, unique=True, db_index=True)
    email = models.EmailField(
        max_length=255, unique=False, db_index=True, null=True, blank=True
    )
    billed_recipient = models.OneToOneField(
        "customer.Recipient",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="billed_user",
    )

    first_name = models.CharField(max_length=50, null=True, blank=True)
    last_name = models.CharField(max_length=50, null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    extra = models.JSONField(default=dict, blank=True)
    is_created_by_admin = models.BooleanField(default=False)

    date_joined = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Data fetched using id pin provided for the first billed recipient
    id_pin = models.CharField(max_length=10, null=True, blank=True)
    id_serial_number = models.CharField(max_length=15, null=True, blank=True)
    real_name = models.CharField(max_length=50, null=True, blank=True)
    real_surname = models.CharField(max_length=50, null=True, blank=True)
    real_patronymic = models.CharField(max_length=50, null=True, blank=True)
    photo_base64 = models.TextField(null=True, blank=True)

    role = models.ForeignKey(
        "customer.Role",
        on_delete=models.PROTECT,
        related_name="users",
        related_query_name="user",
    )

    registered_promo_code = models.ForeignKey(
        "fulfillment.PromoCode",
        related_name="registered_users",
        related_query_name="registered_user",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    prefered_warehouse = models.ForeignKey(
        "fulfillment.Warehouse",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    objects = UserManager()

    USERNAME_FIELD = "full_phone_number"
    EMAIL_FIELD = "email"

    class Meta:
        db_table = "user"
        ordering = ["-date_joined"]
        constraints = [
            models.UniqueConstraint(
                fields=["email"],
                name="unique_email_when_is_active",
                condition=models.Q(is_active=True),
            )
        ]

    def __str__(self):
        return "%s %s [%s]" % (self.first_name, self.last_name, self.full_phone_number)

    @property
    def full_name(self):
        first_name = self.first_name and self.first_name.strip()
        last_name = self.last_name and self.last_name.strip()

        if first_name or last_name:
            name = "%s %s" % (first_name or "", last_name or "")
            return name.strip()

        return None

    @property
    def as_customer(self):
        # Return self, otherwise legacy code may be broken
        return self

    @property
    def phone_is_verified(self):
        return self.extra.get("sms_verified", False)

    @property
    def email_is_verified(self):
        return self.extra.get("email_verified", False)

    @property
    def has_complete_profile(self):
        return self.is_completed

    @property
    def active_balance(self):
        from core.models import Currency

        currency = Currency.objects.filter(
            code=settings.USER_BALANCE_CURRENCY_CODE
        ).first()
        if currency:
            return self.get_balance(currency)
        return None

    @property
    def identifier(self):
        return self.client_code

    @property
    def user_id(self):
        """
        For notification event class that relies on user_id property of object.
        Made an exception for this user model.
        """
        return self.pk

    def get_balance(self, currency):
        """Will create balance if necessary."""
        balance, created = self.balances.get_or_create(currency=currency)
        return balance

    def save(self, *args, **kwargs):
        if not self.client_code:
            # Strip country code with plus sign and prepend 0 digit to client code
            self.client_code = self._generate_new_client_code(prefix="0")

        if self.email:
            self.email = self.email.lower()

        return super().save(*args, **kwargs)

    def set_verification_code(self, domain="sms", send=True):
        # NOTE: `domain` variable here is useless.
        # When it was written it is assumed that verification code must be
        # sent to email too. But it is unnecessary now.
        # FIXME: Remove usage of `domain` variable
        if settings.DEBUG:
            random_code = "123456"
        else:
            random_code = self._generate_random_code(length=6)

        expire_time = timezone.now() + timedelta(minutes=5)

        self.extra["%s_verification_code" % domain] = random_code
        self.extra["%s_verification_expire" % domain] = expire_time.timestamp()
        self.save(update_fields=["extra"])

        if send:
            transaction.on_commit(
                lambda: send_sms_with_random_code(self.id, random_code)
            )

    def send_reset_password_sms(self, send=True):
        users = User.objects.select_for_update().filter(id=self.id)

        with transaction.atomic():
            user = users.first()  # the same logic as in check_reset_password_sms_code

            # Check if 60 seconds are passed
            last_send_time = self.extra.get("password_reset_code_send_time", None)
            now = timezone.now().timestamp()

            can_resend = False
            # If it was not sent at all, send it
            if not last_send_time or now - last_send_time > 60:
                can_resend = True

            if can_resend:
                if settings.DEBUG:
                    random_code = "123456"
                else:
                    random_code = self._generate_random_code(length=6)

                self.extra["password_reset_code"] = random_code
                self.extra["password_reset_code_send_time"] = now
                self.extra["password_reset_code_expire_time"] = now + 120
                self.extra["retry_count"] = 0
                self.save(update_fields=["extra"])

                if send:
                    transaction.on_commit(self._send_reset_password_sms)

    def _send_reset_password_sms(self):
        """
        Actually send reset code by SMS.
        """
        send_sms_with_random_code(self.id, self.extra["password_reset_code"])

    def check_reset_password_sms_code(self, code, new_password=None):
        # Check if not expired
        users = User.objects.select_for_update().filter(id=self.id)

        with transaction.atomic():
            user = users.first()  # get the first user, we will get that user 100%!
            expire_time = user.extra.get("password_reset_code_expire_time")
            retry_count = self.extra.get("retry_count", 0)
            now = timezone.now().timestamp()

            if not expire_time or now - expire_time > 130 or retry_count > 2:
                user._clear_password_reset_data(commit=True)
                return False

            current_code = self.extra.get("password_reset_code", None)
            if code == current_code:
                if new_password:
                    user._clear_password_reset_data(commit=True)
                    user.set_password(new_password)
                    user.save(update_fields=["password"])

                return True

            self.extra["retry_count"] = retry_count + 1
            self.save(update_fields=["extra"])
            return False

    def _clear_password_reset_data(self, commit=True):
        fields = [
            "retry_count",
            "password_reset_code",
            "password_reset_code_send_time",
            "password_reset_code_expire_time",
        ]

        for field in fields:
            if self.extra.get(field):
                del self.extra[field]

        if commit:
            self.save(update_fields=["extra"])

    def send_activation_email(self, email):
        from domain.conf import Configuration
        from domain.services import create_notification
        from fulfillment.models import NotificationEvent as EVENETS

        now = timezone.now().timestamp()

        users = User.objects.select_for_update().filter(id=self.id)

        # Check email send time
        with transaction.atomic():
            user = users.first()
            last_time_sent = self.extra.get("email_verification_send_time")

            if not last_time_sent or (now - last_time_sent) > 120:
                # Can send email again
                self.extra["email_verification_send_time"] = now
                self.extra["email_verified"] = False
                self.email = email
                uid = urlsafe_base64_encode(force_bytes(self.pk))
                token = account_activation_token.make_token(self)
                conf = Configuration()
                link = conf.get_activation_email_link(uid, token)

                create_notification(
                    self,
                    EVENETS.ON_USER_EMAIL_PREACTIVATE,
                    [
                        {
                            "activation_link": mark_safe(link),
                            "sms_code": self.extra.get("sms_verification_code", ""),
                        },
                        self,
                    ],
                    lang_code=translation.get_language(),
                )

                self.save(update_fields=["email", "extra"])

    def confirm_email(self, token):
        if self.email_is_verified:
            raise AlreadyVerifiedError

        if account_activation_token.check_token(self, token):
            self.extra["email_verified"] = True
            self.save(update_fields=["extra"])
            return True

        raise EmailConfirmationError

    def get_verification_code(self, domain="sms"):
        return self.extra.get("%s_verification_code" % domain, None)

    def get_verification_code_expire(self, domain="sms"):
        return self.extra.get("%s_verification_expire" % domain, None)

    def is_expired(self, expire_time):
        return expire_time is None or timezone.now().timestamp() > expire_time

    def check_verification_code(self, code, domain="sms", activate=True):
        real_code = self.get_verification_code(domain=domain)
        expire_time = self.get_verification_code_expire(domain=domain)

        # Check expiration
        if self.is_expired(expire_time):
            return False

        # If real code is None then code is always invalid
        verified = real_code is not None and real_code == code

        if verified:
            self.extra["%s_verified" % domain] = True

            if activate:
                self.activate(update_fields=["extra"])
            else:
                self.save(update_fields=["extra"])

        return verified

    def activate(self, update_fields=[]):
        self.is_active = True
        self.date_joined = timezone.now()
        self.save(update_fields=update_fields + ["is_active", "date_joined"])

    def _generate_random_code(self, length=6):
        digits = list(string.digits)
        return "".join(secrets.choice(digits) for _ in range(length))

    def _generate_new_client_code(self, prefix=""):
        """
        Generates client code based on phone number
        """
        phone_number = self.full_phone_number

        # Try to remove country code
        code = phone_number
        stripped_phone_code = False

        for country_phone_code in Country.objects.values_list("phone_code", flat=True):
            if phone_number.startswith(country_phone_code):
                stripped_phone_code = True
                code = prefix + phone_number.replace(country_phone_code, "")

        if not stripped_phone_code:
            code = code.strip("+")

        if User.objects.filter(client_code=code).exists():
            return self._generate_new_client_code(prefix=self._get_next_letter(prefix))

        return code

    def _get_next_letter(self, current_letter):
        letters = list(string.ascii_uppercase)

        try:
            return letters[letters.index(current_letter) % len(letters)]
        except ValueError:
            return letters[0]

    def check_password(self, password):
        from domain.conf import Configuration
        from customer.models.common_password import check_password_for_user

        password_is_good = super().check_password(password)

        if not password_is_good and Configuration()._conf.common_password_is_enabled:
            return check_password_for_user(self.id, password)

        return password_is_good

    @property
    def is_completed(self):
        return self.recipients.filter(is_deleted=False).exists()


# class Profile(models.Model):
#     MALE = "M"
#     FEMALE = "F"

#     GENDERS = ((MALE, msg.MALE_SEX), (FEMALE, msg.FEMALE_SEX))

#     AZE_SERIAL = "AZE"
#     AA_SERIAL = "AA"

#     ID_SERIALS = ((AZE_SERIAL, "AZE"), (AA_SERIAL, "AA"))

#     user = models.OneToOneField("customer.User", on_delete=models.CASCADE)

#     # warehouse = models.ForeignKey(
#     #     "fulfillment.Warehouse", on_delete=models.SET_NULL, null=True, blank=True
#     # )
#     # address = models.CharField(max_length=50, null=True, blank=True)
#     gender = models.CharField(max_length=1, choices=GENDERS, null=True, blank=True)
#     birth_date = models.DateField(null=True, blank=True)

#     id_serial = models.CharField(max_length=3, choices=ID_SERIALS, null=True)
#     id_number = models.CharField(max_length=8, null=True, blank=True)
#     id_pin = models.CharField(max_length=7, null=True, blank=True)

#     extra = models.JSONField(default=dict, blank=True, null=True)

#     class Meta:
#         db_table = "profile"

#     def __str__(self):
#         return "Profile [%s]" % (self.user)

#     @property
#     def is_completed(self):
#         return all(
#             [self.gender, self.birth_date, self.id_serial, self.id_pin, self.id_number,]
#         )

#     @property
#     def identifier(self):
#         return "%s %s" % (self.id_serial, self.id_number)
