from django_filters.rest_framework import FilterSet

from customer.models import Customer


class CustomerFilter(FilterSet):
    class Meta:
        model = Customer
        fields = {
            "first_name": ["exact", "icontains"],
            "last_name": ["exact", "icontains"],
            "client_code": ["exact", "icontains"],
            "full_phone_number": ["exact", "icontains"],
            "is_active": ["exact"],
            "is_staff": ["exact"],
            "date_joined": [
                "day__exact",
                "day__gte",
                "day__lte",
                "month__exact",
                "month__gte",
                "month__lte",
                "year__exact",
                "year__gte",
                "year__lte",
            ],
            "first_name": ["exact", "icontains"],
            # "profile__gender": ["exact"],
            # "profile__birth_date": [
            #     "day__exact",
            #     "day__gte",
            #     "day__lte",
            #     "month__exact",
            #     "month__gte",
            #     "month__lte",
            #     "year__exact",
            #     "year__gte",
            #     "year__lte",
            # ],
            # "profile__id_serial": ["exact", "contains"],
            # "profile__id_number": ["exact", "contains"],
            # "profile__id_pin": ["exact", "contains"],
        }
