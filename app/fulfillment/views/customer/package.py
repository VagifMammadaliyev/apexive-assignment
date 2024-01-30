from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_list_or_404, get_object_or_404
from django.utils.translation import ugettext_lazy as _
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from domain.services import promote_status, save_user_country_log
from domain.exceptions.customer import UncompleteProfileError
from domain.exceptions.logic import InvalidActionError
from fulfillment.models import Package, StatusEvent, Status
from fulfillment.serializers.common import StatusEventSerializer
from fulfillment.serializers.customer import (
    ArchiveSerializer,
    BulkArchiveSerializer,
    PackageDetailedSerializer,
    PackageReadSerializer,
    PackageWriteSerializer,
)
from fulfillment.views.utils import filter_by_archive_status


class PackageListCreateApiView(generics.ListCreateAPIView):
    throttle_scope = "light"

    def post(self, request, *args, **kwargs):
        # if not request.user.has_complete_profile:
        #     raise UncompleteProfileError

        return super().post(request, *args, **kwargs)

    def get_queryset(self):
        statuses = self.request.query_params.getlist("status")
        packages = self.request.user.packages.filter(shipment__isnull=True)
        packages = filter_by_archive_status(packages, self.request)

        if statuses and all(statuses):
            packages = packages.filter(status__in=statuses)

        from_date = self.request.query_params.get("from")
        if from_date:
            try:
                packages = packages.filter(created_at__gte=from_date)
            except ValidationError:
                pass

        to_date = self.request.query_params.get("to")
        if to_date:
            try:
                packages = packages.filter(created_at__lte=to_date)
            except ValidationError:
                pass

        return packages.order_by("-updated_at").select_related()

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            return PackageReadSerializer
        return PackageWriteSerializer

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context["user"] = self.request.user

        if self.request.method == "POST":
            context["creating"] = True

        return context

    def perform_create(self, serializer):
        status_codename = "awaiting"
        status = Status.objects.get(type=Status.PACKAGE_TYPE, codename=status_codename)
        source_country = serializer.validated_data["source_country"]

        package = serializer.save(
            user=self.request.user,
            status=status,
        )

        save_user_country_log(package.user_id, package.source_country_id)


class PackageRetrieveUpdateDestroyApiView(generics.RetrieveUpdateDestroyAPIView):
    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            return PackageDetailedSerializer
        return PackageWriteSerializer

    def get_object(self):
        tracking_code = self.kwargs.get("tracking_code")
        package = self.request.user.packages.filter(
            Q(user_tracking_code=tracking_code) | Q(admin_tracking_code=tracking_code)
        ).first()

        if not package:
            raise Http404

        method = self.request.method

        if method == "DELETE" and not package.can_be_deleted_by_user:
            raise InvalidActionError
        elif method in ["PATCH", "PUT"] and not package.can_be_edited_by_user:
            raise InvalidActionError

        return package

    def perform_update(self, serializer):
        serializer.instance._must_recalculate_total_price = True
        serializer.save()

    def perform_destroy(self, package):
        promote_status(
            package, Status.objects.get(type=Status.PACKAGE_TYPE, codename="deleted")
        )

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context["user"] = self.request.user

        return context


@api_view(["GET"])
def package_timeline_view(request, tracking_code):
    events = get_list_or_404(StatusEvent, package__tracking_code=tracking_code)
    return Response(
        StatusEventSerializer(events, many=True).data, status=status.HTTP_200_OK
    )


@api_view(["POST"])
def package_archive_view(request, tracking_code):
    package = get_object_or_404(
        Package,
        Q(user_tracking_code=tracking_code) | Q(admin_tracking_code=tracking_code),
        user=request.user,
    )

    serializer = ArchiveSerializer(data={"instance": package})
    serializer.is_valid(raise_exception=True)
    serializer.perform_archive()

    return Response(PackageReadSerializer(package).data, status=status.HTTP_200_OK)


@api_view(["POST"])
def package_bulk_archive_view(request):
    serializer = BulkArchiveSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    ids = serializer.validated_data["ids"]
    packages = get_list_or_404(
        Package,
        Q(user_tracking_code__in=ids) | Q(admin_tracking_code__in=ids),
        user=request.user,
    )
    serializer.perform_archive(packages)

    return Response(status=status.HTTP_204_NO_CONTENT)
