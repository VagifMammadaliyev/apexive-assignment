from django.db.models import Q
from django.utils.decorators import method_decorator
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from domain.logging.utils import generic_logging
from customer.models import Role
from customer.serializers import RoleSerializer
from customer.permissions import IsOntimeStaffUser, IsOntimeAdminUser
from core.models import Country, Currency, MobileOperator, City
from fulfillment.decorators import no_lang_fallback
from core.serializers import admin as core_serializers
from core import filters


@api_view(["GET"])
@permission_classes([IsOntimeStaffUser])
def timezone_list_view(request):
    return Response(
        [tz for tz, _ in list(Country.TIMEZONES)], status=status.HTTP_200_OK
    )


@api_view(["GET"])
@permission_classes([IsOntimeAdminUser])
def role_list_view(request):
    return Response(RoleSerializer(Role.objects.all(), many=True).data)


@generic_logging
class CountryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOntimeAdminUser]
    queryset = Country.objects.select_related()
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.CountryFilter

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsOntimeStaffUser()]

        return super().get_permissions()

    def paginate_queryset(self, *args, **kwargs):
        if "compact" in self.request.query_params:
            return None

        return super().paginate_queryset(*args, **kwargs)

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            if "compact" in self.request.query_params:
                return core_serializers.CountryCompactSerializer
            if self.action == "list":
                return core_serializers.CountryReadSerializer
            return core_serializers.CountryTranslatedReadSerializer
        return core_serializers.CountryWriteSerializer


@generic_logging
class CurrencyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOntimeAdminUser]
    queryset = Currency.objects.select_related()
    serializer_class = core_serializers.CurrencyTranslatedSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.CurrencyFilter

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsOntimeStaffUser()]

        return super().get_permissions()

    def paginate_queryset(self, *args, **kwargs):
        if "compact" in self.request.query_params:
            return None

        return super().paginate_queryset(*args, **kwargs)

    def get_serializer_class(self, *args, **kwargs):
        if "compact" in self.request.query_params:
            return core_serializers.CurrencyCompactSerializer
        if self.action == "list":
            return core_serializers.CurrencySerializer
        return super().get_serializer_class(*args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        if "warehouseman" in self.request.query_params:
            # Check if it is warehouseman
            warehouseman_profile = getattr(
                self.request.user, "warehouseman_profile", None
            )
            if warehouseman_profile:
                return queryset.filter(
                    Q(country__id=warehouseman_profile.warehouse.country_id) | Q(rate=1)
                )

        return queryset


@generic_logging
class MobileOperatorViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOntimeAdminUser]
    queryset = MobileOperator.objects.select_related()

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsOntimeStaffUser()]

        return super().get_permissions()

    def paginate_queryset(self, *args, **kwargs):
        if "compact" in self.request.query_params:
            return None

        return super().paginate_queryset(*args, **kwargs)

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            return core_serializers.MobileOperatorReadSerializer
        return core_serializers.MobileOperatorWriteSerializer


@generic_logging
class CityViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOntimeAdminUser]
    queryset = City.objects.order_by("country")
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.CityFilter

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsOntimeStaffUser()]

        return super().get_permissions()

    def paginate_queryset(self, *args, **kwargs):
        if "compact" in self.request.query_params:
            return None

        return super().paginate_queryset(*args, **kwargs)

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            if "compact" in self.request.query_params:
                return core_serializers.CityCompactSerializer
            if self.action == "list":
                return core_serializers.CityReadSerializer
            return core_serializers.CityTranslatedReadSerializer
        return core_serializers.CityWriteSerializer
