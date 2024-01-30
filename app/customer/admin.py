from django.urls import path
from django.shortcuts import redirect, render, reverse
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone
from django.db import transaction as db_transaction

from ontime.admin import admin
from customer.models import (
    User,
    Balance,
    Role,
    Recipient,
    FrozenRecipient,
    CommonPassword,
)
from customer.models.common_password import generate_password
from customer.tasks import fetch_user_data_from_government_resource
from customer.forms import AdminBalanceUpdateForm


@admin.register(Role)
class Role(admin.ModelAdmin):
    list_display = ["type"]


class BalanceInlineAdmin(admin.StackedInline):
    model = Balance
    extra = 0
    max_num = 1
    readonly_fields = ["currency", "amount"]
    exclude = ["extra"]

    # autocomplete_fields = ["currency"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    autocomplete_fields = [
        "billed_recipient",
        "registered_promo_code",
        "prefered_warehouse",
    ]
    change_form_template = "admin/customer/customer/change_form.html"
    list_filter = ["is_staff", "role"]
    search_fields = [
        "client_code__icontains",
        "first_name__icontains",
        "last_name__icontains",
        "email__icontains",
        "full_phone_number__icontains",
    ]
    fieldsets = [
        (None, {"fields": ["client_code", "full_phone_number", "email", "password"]}),
        (
            "Other info",
            {
                "fields": [
                    "first_name",
                    "last_name",
                    "date_joined",
                    "role",
                    "is_staff",
                    "is_active",
                    "is_superuser",
                    "is_created_by_admin",
                    "billed_recipient",
                    "registered_promo_code",
                    "prefered_warehouse",
                    "extra",
                ],
            },
        ),
        (
            "Permissions & Groups",
            {
                "fields": [
                    "groups",
                    "user_permissions",
                ]
            },
        ),
        (
            "Other info",
            {
                "fields": [
                    "id_pin",
                    "id_serial_number",
                    "real_name",
                    "real_surname",
                    "real_patronymic",
                    "photo_base64",
                ]
            },
        ),
    ]
    add_fieldsets = [
        (
            None,
            {
                "fields": [
                    "client_code",
                    "full_phone_number",
                    "email",
                    "role",
                    "is_staff",
                    "is_active",
                    "password1",
                    "password2",
                    "billed_recipient",
                    "extra",
                ]
            },
        ),
    ]
    list_display = [
        "client_code",
        "full_phone_number",
        "email",
        "first_name",
        "last_name",
    ]
    ordering = ["-date_joined"]
    inlines = [BalanceInlineAdmin]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:pk>/resend/email-activation/",
                self.admin_site.admin_view(self.resend_verification_email_view),
                name="resend-email-activation-core-admin",
            ),
            path(
                "<int:pk>/deactivate-email/",
                self.admin_site.admin_view(self.deactivate_email_view),
                name="deactivate-email-core-admin",
            ),
            path(
                "<int:pk>/activate-email/",
                self.admin_site.admin_view(self.activate_email_view),
                name="activate-email-core-admin",
            ),
            path(
                "<int:pk>/fetch-gov-info/",
                self.admin_site.admin_view(self.fetch_gov_info),
                name="fetch-gov-info-core-admin",
            ),
            path(
                "<int:pk>/update-balance/",
                self.admin_site.admin_view(self.update_balance),
                name="update-balance",
            ),
        ]
        return custom_urls + urls

    def resend_verification_email_view(self, request, pk):
        user = self._get_user(request, pk)

        if user and user.email and not user.email_is_verified:
            user.send_activation_email(user.email)
        return self._get_redirect(user.pk)

    def activate_email_view(self, request, pk):
        user = self._get_user(request, pk)
        if user:
            user.extra["email_verified"] = True
            user.extra["email_verification_send_time"] = None
            user.save(update_fields=["extra"])
        return self._get_redirect(user.pk)

    def deactivate_email_view(self, request, pk):
        user = self._get_user(request, pk)
        if user:
            user.extra["email_verified"] = False
            user.extra["email_verification_send_time"] = None
            user.save(update_fields=["extra"])
        return self._get_redirect(user.pk)

    def fetch_gov_info(self, request, pk):
        # We will run this process in the same thread.
        # Don't use celery task here because page may load
        # faster than celery complete the task.
        user = self._get_user(request, pk)

        if user:
            if not user.billed_recipient_id:
                messages.error(
                    request, "User does not have billed recipient, can't fetch data"
                )
            fetch_user_data_from_government_resource(user.billed_recipient_id)

        return self._get_redirect(user.pk)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.is_created_by_admin = True

        if obj.is_active and not obj.date_joined:
            obj.date_joined = timezone.now()

        super().save_model(request, obj, form, change)

    def has_delete_permission(self, *args, **kwargs):
        return False

    def _get_user(self, request, pk):
        user = User.objects.filter(id=pk).first()

        if not user:
            messages.error(request, f"No user found with id {pk}")

        return user

    def update_balance(self, request, pk):
        from fulfillment.models import Transaction
        from domain.services import complete_payments

        user = self._get_user(request, pk)
        if user:
            if request.method == "GET":
                form = AdminBalanceUpdateForm(user_pk=pk)
                return render(
                    request,
                    "admin/customer/balance-update.html",
                    {"form": form, "user": user},
                )

            elif request.method == "POST":
                form = AdminBalanceUpdateForm(user_pk=pk, data=request.POST)

                if form.is_valid():
                    balance = form.cleaned_data["balance"]
                    purpose = form.cleaned_data["purpose"]
                    amount = form.cleaned_data["amount"]

                    with db_transaction.atomic():
                        transaction = Transaction.objects.create(
                            user=user,
                            amount=amount,
                            currency_id=balance.currency_id,
                            completed=False,
                            type=Transaction.CASH,
                            purpose=purpose,
                        )

                        complete_payments([transaction])
                        action = (
                            "added to"
                            if transaction.purpose == Transaction.BALANCE_INCREASE
                            else "charged from"
                        )
                        msg = f"{amount}{balance.currency.symbol} {action} {user.full_name}'s balance"
                        self.log_change(
                            request, user, message=f"{msg} by {request.user}"
                        )
                        messages.success(
                            request,
                            msg,
                        )
                else:
                    return render(
                        request,
                        "admin/customer/balance-update.html",
                        {"form": form, "user": user},
                    )

        return self._get_redirect(user.pk)

    def _get_redirect(self, user_pk):
        return redirect(reverse("admin:customer_user_change", args=[user_pk]))


# @admin.register(Address)
# class AddressAdmin(admin.ModelAdmin):
#     autocomplete_fields = ["user", "country", "nearby_warehouse"]
#     search_fields = [
#         "user__client_code__icontains",
#         "user__full_phone_number__icontains",
#         "user__first_name__icontains",
#         "user__last_name__icontains",
#         "user__email__icontains",
#         "recipient_first_name__icontains",
#         "recipient_last_name__icontains",
#         "recipient_phone_number__icontains",
#     ]


@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    autocomplete_fields = ["user", "city"]
    list_display = [
        "full_name",
        "title",
        "id_pin",
        "phone_number",
        "address",
        "is_deleted",
    ]
    search_fields = [
        "user__client_code__icontains",
        "user__full_phone_number__icontains",
        "user__first_name__icontains",
        "user__last_name__icontains",
        "user__email__icontains",
        "first_name__icontains",
        "last_name__icontains",
        "phone_number__icontains",
    ]


@admin.register(FrozenRecipient)
class FrozenRecipientAdmin(admin.ModelAdmin):
    autocomplete_fields = ["user"]
    list_display = [
        "full_name",
        "id_pin",
        "phone_number",
    ]
    search_fields = [
        "user__client_code__icontains",
        "user__full_phone_number__icontains",
        "user__first_name__icontains",
        "user__last_name__icontains",
        "user__email__icontains",
        "first_name__icontains",
        "last_name__icontains",
        "phone_number__icontains",
    ]


@admin.register(CommonPassword)
class CommonPasswordAdmin(admin.ModelAdmin):
    readonly_fields = ["generated_by", "created_at", "expires_on"]
    exclude = ["hashed_password"]
    list_display = ["generated_by", "created_at", "is_expired"]
    change_list_template = "admin/common_password/change_list.html"

    def get_urls(self):
        original_urls = super().get_urls()

        custom_urls = [
            path(
                "new-common-password/",
                self.admin_site.admin_view(self.generate_common_password),
                name="common-password-create",
            ),
        ]

        return custom_urls + original_urls

    def is_expired(self, common_password):
        return common_password.expires_on < timezone.now()

    def has_change_permission(self, *args, **kwargs):
        return False

    def has_delete_permission(self, *args, **kwargs):
        return False

    def generate_common_password(self, request):
        if not request.user.has_perm("customer.add_common_password"):
            raise PermissionDenied

        new_password = generate_password()
        common_password_obj = CommonPassword(
            generated_by=request.user,
        )
        common_password_obj.set_password(new_password)
        common_password_obj.save()

        return render(
            request,
            "admin/common_password/result.html",
            context={"password": new_password, "common_password": common_password_obj},
        )
