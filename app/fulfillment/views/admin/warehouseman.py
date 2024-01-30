from itertools import chain

from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum, Count, Prefetch, Exists, OuterRef
from django.db import transaction as db_transaction
from django.utils import timezone
from django.http import Http404
from django.core.files import File
from django.conf import settings
from rest_framework import status, generics, mixins, viewsets, views, parsers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from domain.services import (
    accept_incoming_packages,
    accept_incoming_shipment,
    create_uncomplete_transaction_for_shipment,
    confirm_shipment_properties,
    mark_instance_as_serviced,
)
from domain.logging.utils import generic_logging, log_generic_method, log_action, CHANGE
from domain.utils.documents import ManifestGenerator
from domain.conf import Configuration
from core.models import City
from fulfillment.models import (
    Package,
    Shipment,
    Box,
    Transportation,
    Status,
    Warehouse,
    PackageAdditionalService,
    ShipmentAdditionalService,
    PackageAdditionalServiceAttachment,
    ShipmentAdditionalServiceAttachment,
)
from fulfillment.serializers.admin import warehouseman as wh_serializers
from fulfillment.views.utils import UserDeclaredFilterMixin
from fulfillment.filters import (
    ShipmentFilter,
    PackageFilter,
    TransportationFilter,
    WarehouseFilter,
)
from fulfillment.tasks import send_manifest_by_email
from customer.models import Recipient
from customer.permissions import IsWarehouseman, IsOntimeAdminUser


@api_view(["POST"])
@permission_classes([IsWarehouseman | IsOntimeAdminUser])
def accept_incoming_package_view(request):
    tracking_code = request.data.get("tracking_code", None)
    packages = []
    if tracking_code:
        packages = Package.objects.filter(
            Q(admin_tracking_code__iexact=tracking_code)
            | Q(user_tracking_code__iexact=tracking_code),
        )

    accepted_packages = accept_incoming_packages(
        packages,
        request.user.warehouseman_profile,
        override_tracking_code=request.data.get("new_tracking_code"),
    )

    return Response(
        wh_serializers.PackageDetailedSerializer(
            accepted_packages, many=True, context={"request": request}
        ).data
    )


class ShipmentOrderedServiceListApiView(generics.ListAPIView):
    permission_classes = [IsWarehouseman | IsOntimeAdminUser]
    serializer_class = wh_serializers.ShipmentAdditionalServiceReadSerializer
    pagination_class = None

    def get_queryset(self):
        warehouseman = self.request.user.warehouseman_profile
        shipment = get_object_or_404(
            Shipment.objects.filter(current_warehouse_id=warehouseman.warehouse_id),
            number=self.kwargs.get("number"),
        )

        return shipment.ordered_services.all()


@api_view(["POST"])
@permission_classes([IsWarehouseman | IsOntimeAdminUser])
@db_transaction.atomic
def mark_single_shipment_service_as_completed_view(request, number, ordered_service_id):
    attachments = ShipmentAdditionalServiceAttachment.objects.filter(
        ordered_service=OuterRef("pk")
    ).values("pk")
    ShipmentAdditionalService.objects.annotate(
        attachments_exists=Exists(attachments),
    ).filter(
        (Q(service__needs_attachment=True) & Q(attachments_exists=True))
        | (Q(service__needs_attachment=False)),
        shipment__number=number,
        id=ordered_service_id,
    ).update(
        is_completed=True
    )

    incomplete_services = ShipmentAdditionalService.objects.filter(
        is_completed=False, shipment=OuterRef("pk")
    ).values("pk")
    shipment = (
        Shipment.objects.annotate(has_incomplete_service=Exists(incomplete_services))
        .filter(number=number, has_incomplete_service=False)
        .first()
    )

    if shipment:
        mark_instance_as_serviced(shipment)
    return Response({"status": "OK"})


class PackageOrderedServiceListApiView(generics.ListAPIView):
    permission_classes = [IsWarehouseman | IsOntimeAdminUser]
    serializer_class = wh_serializers.PackageAdditionalServiceReadSerializer
    pagination_class = None

    def get_queryset(self):
        warehouseman = self.request.user.warehouseman_profile
        package = get_object_or_404(
            Package.objects.filter(current_warehouse_id=warehouseman.warehouse_id),
            pk=self.kwargs.get("pk"),
        )

        return package.ordered_services.all()


@api_view(["POST"])
@permission_classes([IsWarehouseman | IsOntimeAdminUser])
@db_transaction.atomic
def mark_single_package_service_as_completed_view(
    request, package_id, ordered_service_id
):
    attachments = PackageAdditionalServiceAttachment.objects.filter(
        ordered_service=OuterRef("pk")
    ).values("pk")
    PackageAdditionalService.objects.annotate(
        attachments_exists=Exists(attachments),
    ).filter(
        (Q(service__needs_attachment=True) & Q(attachments_exists=True))
        | (Q(service__needs_attachment=False)),
        package__id=package_id,
        id=ordered_service_id,
    ).update(
        is_completed=True
    )

    incomplete_services = PackageAdditionalService.objects.filter(
        is_completed=False, package=OuterRef("pk")
    ).values("pk")
    package = (
        Package.objects.annotate(has_incomplete_service=Exists(incomplete_services))
        .filter(id=package_id, has_incomplete_service=False)
        .first()
    )

    if package:
        mark_instance_as_serviced(package)
    return Response({"status": "OK"})


class OrderedServiceFulFillApiView(views.APIView):
    """This view is currently used for attachments for ordered services"""

    permission_classes = [IsWarehouseman | IsOntimeAdminUser]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_service_model(self):
        if "for_shipments" in self.request.query_params:
            return ShipmentAdditionalService
        return PackageAdditionalService

    def get_attachment_model(self):
        if "for_shipments" in self.request.query_params:
            return ShipmentAdditionalServiceAttachment
        return PackageAdditionalServiceAttachment

    def get_queryset(self):
        return self.get_service_model().objects.filter(service__needs_attachment=True)

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs.get("pk"))

    @db_transaction.atomic
    def post(self, request, *args, **kwargs):
        service = self.get_object()

        if request.FILES:
            for file in request.data.getlist("attachment"):
                self.get_attachment_model().objects.create(
                    ordered_service=service, file=File(file)
                )

            return Response({"status": "OK"})

        return Response({"status": "No files"}, status=status.HTTP_400_BAD_REQUEST)


class PackageByClientApiView(generics.ListAPIView):
    serializer_class = wh_serializers.PackageReadSerializer
    permission_classes = [IsWarehouseman | IsOntimeAdminUser]
    # filter_backends = [DjangoFilterBackend]
    # filterset_class = PackageFilter

    def get_queryset(self):
        warehouseman = self.request.user.warehouseman_profile
        return Package.objects.annotate(
            has_services=Exists(
                PackageAdditionalService.objects.filter(package=OuterRef("pk")).values(
                    "pk"
                )
            )
        ).filter(
            is_accepted=False,
            # status__codename='awaiting',
            source_country_id=warehouseman.warehouse.country_id,
            user_id=self.request.query_params.get("client"),
        )


class PackageDashboardApiView(generics.ListAPIView):
    permission_classes = [IsWarehouseman | IsOntimeAdminUser]
    serializer_class = wh_serializers.PackageReadSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = PackageFilter

    def get_queryset(self):
        warehouseman = self.request.user.warehouseman_profile
        return (
            Package.objects.annotate(
                has_services=Exists(
                    PackageAdditionalService.objects.filter(
                        package=OuterRef("pk")
                    ).values("pk")
                )
            )
            .filter(
                is_accepted=True,
                current_warehouse=warehouseman.warehouse_id,
                shipment__isnull=True,
            )
            .order_by("-id")
            .prefetch_related("products__photos", "photos")
        )


class PackageRetrieveUpdateApiView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsWarehouseman | IsOntimeAdminUser]

    def get_queryset(self):
        warehouseman = self.request.user.warehouseman_profile
        return Package.objects.filter(
            is_accepted=True, current_warehouse=warehouseman.warehouse_id
        )

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            return wh_serializers.PackageDetailedSerializer
        return wh_serializers.PackageWriteSerializer


class ShipmentDashboardApiView(generics.ListAPIView, UserDeclaredFilterMixin):
    permission_classes = [IsWarehouseman | IsOntimeAdminUser]
    serializer_class = wh_serializers.ShipmentReadSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = ShipmentFilter

    def get_queryset(self):
        conf = Configuration()
        warehouseman = self.request.user.warehouseman_profile
        statuses = self.request.query_params.getlist("status")
        shipments = Shipment.objects.annotate(
            has_services=Exists(
                ShipmentAdditionalService.objects.filter(
                    shipment=OuterRef("pk")
                ).values("pk")
            )
        ).filter(
            current_warehouse_id=warehouseman.warehouse_id,
        )
        shipments = conf.annotate_by_exlcude_from_smart_customs(shipments)
        shipments = self.filter_by_user_declared(shipments)

        package_id = self.request.query_params.get("package_id")

        if "q" in self.request.query_params:
            query = self.request.query_params.get("q")
            rel_pack = Package.objects.filter(
                Q(user_tracking_code__icontains=query)
                | Q(admin_tracking_code__icontains=query)
                | (Q(id=package_id) if package_id else Q()),
                shipment_id=OuterRef("id"),
            ).values("id")
            shipments = shipments.annotate(pack_match=Exists(rel_pack)).filter(
                Q(number__icontains=query) | Q(pack_match=True)
            )
        elif package_id:
            rel_pack = Package.objects.filter(
                id=package_id,
                shipment_id=OuterRef("id"),
            ).values("id")
            shipments = shipments.annotate(pack_match=Exists(rel_pack)).filter(
                pack_match=True
            )

        if statuses and all(statuses):
            shipments = shipments.filter(status__in=statuses)

        return shipments.order_by("-id").prefetch_related(
            "packages__products__photos", "packages__photos"
        )


class ShipmentRetrieveUpdateApiView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsWarehouseman | IsOntimeAdminUser]

    def get_queryset(self, extra_filters=None):
        extra_filters = extra_filters or dict()
        warehouseman = self.request.user.warehouseman_profile
        conf = Configuration()
        shipments = Shipment.objects.filter(
            current_warehouse_id=warehouseman.warehouse_id, **extra_filters
        )
        shipments = conf.annotate_by_exlcude_from_smart_customs(shipments)
        return shipments

    def get_object(self):
        # We didn't allow to update shipments
        # if it has confirmed properties set to True.
        # But now we must, because only confirmed shipments
        # can be placed in a box, so we will check in a serializer
        # if it has confirmed properties == True, then update only box
        return get_object_or_404(
            self.get_queryset(),
            number=self.kwargs.get("number"),
        )

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            return wh_serializers.ShipmentDetailedSerializer

        if self.request.method == "PATCH":
            current_shipment = self.get_object()
            if current_shipment.can_be_updated_by_warehouseman:
                return wh_serializers.ShipmentWriteSerializer
            return wh_serializers.PlaceShipmentIntoBoxSerializer
        return wh_serializers.ShipmentWriteSerializer

    def perform_update(self, serializer):
        serializer.instance._must_recalculate = True
        serializer.instance._accepted = True
        serializer.instance.declared_price = (
            serializer.instance.calculate_declared_price()
        )  # ...update declared price
        serializer.save()


@generic_logging
class BoxViewSet(viewsets.ModelViewSet):
    permission_classes = [IsWarehouseman | IsOntimeAdminUser]
    pagination_class = None

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)

        current_id = self.kwargs.get("pk")
        if current_id:
            context["current_box_id"] = current_id

        if self.request.method in ["POST", "PATCH", "PUT"]:
            context[
                "current_warehouse_id"
            ] = self.request.user.warehouseman_profile.warehouse_id

        return context

    def get_serializer_class(self, *args, **kwargs):
        if self.action == "retrieve":
            return wh_serializers.BoxDetailedSerializer
        return wh_serializers.BoxSerializer

    def get_queryset(self):
        warehouseman = self.request.user.warehouseman_profile
        return (
            Box.objects.annotate(
                real_total_weight=Sum("shipment__fixed_total_weight"),
                shipments_count=Count("shipment"),
            )
            .filter(
                Q(transportation__isnull=True),
                source_warehouse_id=warehouseman.warehouse_id,
            )
            .order_by("pk")
        )

    def perform_update(self, serializer):
        serializer.save(
            source_warehouse_id=self.request.user.warehouseman_profile.warehouse_id
        )

    def perform_create(self, serializer):
        serializer.save(
            source_warehouse_id=self.request.user.warehouseman_profile.warehouse_id
        )


@api_view(["POST"])
@permission_classes([IsWarehouseman | IsOntimeAdminUser])
def confirm_shipment_properties_view(request, number):
    warehouseman = request.user.warehouseman_profile
    shipment = get_object_or_404(
        Shipment, current_warehouse_id=warehouseman.warehouse_id, number=number
    )
    shipment = confirm_shipment_properties(shipment)
    return Response(wh_serializers.ShipmentReadSerializer(shipment).data)


@generic_logging
class TransportationViewSet(
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
):
    permission_classes = [IsWarehouseman | IsOntimeAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_class = TransportationFilter

    def paginate_queryset(self, *args, **kwargs):
        if "compact" in self.request.query_params:
            return None

        return super().paginate_queryset(*args, **kwargs)

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context[
            "current_warehouse_id"
        ] = self.request.user.warehouseman_profile.warehouse_id
        return context

    def get_queryset(self):
        warehouseman = self.request.user.warehouseman_profile
        transportations = (
            Transportation.objects.annotate(boxes_count=Count("box"))
            .filter(source_city__country_id=warehouseman.warehouse.city.country_id)
            .prefetch_related(
                Prefetch(
                    "boxes",
                    queryset=Box.objects.annotate(
                        real_total_weight=Sum("shipment__fixed_total_weight"),
                        shipments_count=Count("shipment"),
                    ),
                )
            )
        )

        if self.request.method == "GET":
            if "awaiting" in self.request.query_params:
                transportations = transportations.filter(
                    is_completed=False
                    # Q(departure_time__gt=timezone.now())
                    # | Q(departure_time__isnull=True)
                )

            return transportations

        return transportations.filter(is_completed=False)

    def perform_create(self, serializer):
        source_city = serializer.validated_data.get("source_city")
        if not source_city:
            warehouseman = self.request.user.warehouseman_profile
            serializer.save(source_city_id=warehouseman.warehouse.city_id)
        super().perform_create(serializer)

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            if self.action == "retrieve":
                return wh_serializers.TransportationDetailedSerializer
            return wh_serializers.TransportationReadSerializer
        return wh_serializers.TransportationWriteSerializer


@api_view(["POST"])
@permission_classes([IsWarehouseman | IsOntimeAdminUser])
def accept_incoming_shipment_view(request):
    warehouseman = request.user.warehouseman_profile
    shipment_number = request.data.get("shipment_number")

    if settings.DEBUG:
        error_code = None
        if "-" in shipment_number:
            _, error_code = shipment_number.split("-")
        if error_code:
            if error_code == "TO":
                import time

                time.sleep(120)
                return Response()
            return Response(status=int(error_code))

    shipment = get_object_or_404(
        Shipment.objects.filter(
            # Don't filter out, we'll check in domain function
            # destination_warehouse_id=warehouseman.warehouse_id,
            source_warehouse__isnull=False,
        ),
        number=shipment_number,
    )

    accepted_shipment = accept_incoming_shipment(shipment, warehouseman)
    # HACK: WTF?!!
    received_status = Status.objects.get(type=Status.SHIPMENT_TYPE, codename="received")
    if accepted_shipment.status_events.filter(to_status=received_status).exists():
        Shipment.objects.filter(
            id=accepted_shipment.id,
        ).update(status=received_status)
    accepted_shipment.refresh_from_db()

    return Response(
        wh_serializers.AcceptedShipmentReadSerializer(
            accepted_shipment, context={"request": request}
        ).data
    )


@api_view(["POST"])
@permission_classes([IsWarehouseman | IsOntimeAdminUser])
def place_accepted_shipment(request, number):
    warehouseman = request.user.warehouseman_profile
    # FIXME: Remove commmented filter below after you fix issue with status
    shipment = get_object_or_404(
        Shipment.objects.filter(
            # current_warehouse_id=warehouseman.warehouse_id,
            # status__codename="received",
            number=number,
        )
    )

    serializer = wh_serializers.ShelfPlaceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    shelf_number = serializer.validated_data["shelf"]
    shipment.shelf = shelf_number
    Shipment.objects.filter(id=shipment.id).update(shelf=shelf_number)
    shipment.refresh_from_db()

    return Response(wh_serializers.ShipmentReadSerializer(shipment).data)


class ShipmentStatusListApiView(generics.ListAPIView):
    pagination_class = None
    permission_classes = [IsOntimeAdminUser | IsWarehouseman]
    serializer_class = wh_serializers.StatusSerializer
    queryset = Status.objects.filter(type=Status.SHIPMENT_TYPE)


class WarehouseListApiView(generics.ListAPIView):
    permission_classes = [IsOntimeAdminUser | IsWarehouseman]
    serializer_class = wh_serializers.WarehouseReadSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = WarehouseFilter

    def paginate_queryset(self, *args, **kwargs):
        if "compact" in self.request.query_params:
            return None

        return super().paginate_queryset(*args, **kwargs)

    def get_queryset(self):
        warehouseman = self.request.user.warehouseman_profile
        return Warehouse.objects.exclude(
            id=warehouseman.warehouse_id, country__is_base=True
        )


@api_view(["POST"])
@permission_classes([IsWarehouseman | IsOntimeAdminUser])
def mark_package_as_serviced_view(request, pk):
    package = get_object_or_404(Package, pk=pk)
    mark_instance_as_serviced(package)
    return Response({"status": "OK"})


@api_view(["POST"])
@permission_classes([IsWarehouseman | IsOntimeAdminUser])
def mark_shipment_as_serviced_view(request, number):
    shipment = get_object_or_404(Shipment, number=number)
    mark_instance_as_serviced(shipment)
    return Response({"status": "OK"})


class CityListApiView(views.APIView):
    permission_classes = [IsWarehouseman | IsOntimeAdminUser]

    def get(self, request, *args, **kwargs):
        warehouseman = request.user.warehouseman_profile
        cities = City.objects.select_related("country")

        source_cities = list(
            filter(
                lambda c: c.country_id == warehouseman.warehouse.city.country_id, cities
            )
        )
        destination_cities = list(
            filter(lambda c: c.id != warehouseman.warehouse.city_id, cities)
        )

        for city in chain(source_cities, destination_cities):
            city.is_default = False
            if city.id == warehouseman.warehouse.city_id:
                city.is_default = True

        return Response(
            {
                "source_cities": wh_serializers.TransportationCitySerializer(
                    source_cities, many=True
                ).data,
                "destination_cities": wh_serializers.TransportationCitySerializer(
                    destination_cities, many=True
                ).data,
            }
        )


class ProblematicPackageCreateApiView(generics.CreateAPIView):
    permission_classes = [IsWarehouseman | IsOntimeAdminUser]
    serializer_class = wh_serializers.ProblematicPackageWriteSerializer

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context()
        context["current_warehouse"] = self.request.user.warehouseman_profile.warehouse
        return context

    @log_generic_method
    def perform_create(self, serializer):
        warehouseman = self.request.user.warehouseman_profile

        # We will assume that package is arrived today
        today = timezone.now().date()
        package = serializer.save(
            current_warehouse_id=warehouseman.warehouse_id,
            is_problematic=True,
            is_accepted=True,
            arrival_date=today,
            real_arrival_date=today,
            source_country_id=warehouseman.warehouse.city.country_id,
        )


class ShipmentAirwayBillApiView(generics.RetrieveAPIView):
    serializer_class = wh_serializers.AirwayBillSerializer
    lookup_field = "number"
    lookup_url_kwarg = "number"
    permission_classes = [IsWarehouseman | IsOntimeAdminUser]
    queryset = Shipment.objects.filter(
        total_price__isnull=False, total_price_currency__isnull=False
    )  # FIXME: only for this warehouseman


class ExportXMLManifestApiView(views.APIView):
    permission_classes = [IsWarehouseman | IsOntimeAdminUser]

    def get(self, request, *args, **kwargs):
        transportation = get_object_or_404(Transportation, id=self.kwargs.get("pk"))
        log_action(
            CHANGE,
            request.user.id,
            instance=transportation,
            message="Exported XML manifest from warehouseman dashboard",
        )
        send_manifest_by_email.delay(transportation.id)

        return Response({"status": "OK"})


class ExportManifestApiView(views.APIView):
    permission_classes = [IsWarehouseman | IsOntimeAdminUser]

    def get(self, request, *args, **kwargs):
        transportation = get_object_or_404(Transportation, id=self.kwargs.get("pk"))
        log_action(
            CHANGE,
            request.user.id,
            instance=transportation,
            message="Started exporting manifest from warehouseman dashboard",
        )
        generator = ManifestGenerator(transportation=transportation)
        manifest_file = generator.generate_excell()
        return Response(
            {"manifest_file_url": request.build_absolute_uri(manifest_file.url)}
        )


class PackageInvoiceApiView(generics.RetrieveAPIView):
    permission_classes = [IsWarehouseman | IsOntimeAdminUser]
    queryset = Package.objects.all()  # FIXME: Only for this warehouseman
    serializer_class = wh_serializers.PackageInvoiceSerializer

    def get_earliest_order(self, package):
        order = package.related_orders.order_by("created_at").first()
        return order

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context["earliest_order"] = self.get_earliest_order(self.package)
        return context

    def get_object(self):
        self.package = super().get_object()
        return self.package


class ShipmentInvoiceApiView(generics.RetrieveAPIView):
    permission_classes = [IsWarehouseman | IsOntimeAdminUser]
    lookup_field = "number"
    lookup_url_kwarg = "number"
    queryset = Shipment.objects.all()  # FIXME: Only for this warehouseman
    serializer_class = wh_serializers.ShipmentInvoiceSerializer


class AcceptedShipmentReadApiView(generics.RetrieveAPIView):
    permission_classes = [IsWarehouseman | IsOntimeAdminUser]
    lookup_field = "number"
    lookup_url_kwarg = "number"
    queryset = Shipment.objects.all().select_related()
    serializer_class = wh_serializers.AcceptedShipmentDetailedReadSerializer
