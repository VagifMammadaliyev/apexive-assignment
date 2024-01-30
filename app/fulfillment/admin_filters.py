from django.db.models import Q
from django.contrib.admin import SimpleListFilter
from admin_auto_filters.filters import AutocompleteFilter

from domain.conf import Configuration
from fulfillment import models


class CustomerACFilter(AutocompleteFilter):
    title = "Customer"
    field_name = "user"


class SourceCountryACFilter(AutocompleteFilter):
    title = "Source country"
    field_name = "source_country"


class SourceWHACFilter(AutocompleteFilter):
    title = "Source warehouse"
    field_name = "source_warehouse"


class DestinationWHACFilter(AutocompleteFilter):
    title = "Destination warehouse"
    field_name = "destination_warehouse"


class CurrentWHACFilter(AutocompleteFilter):
    title = "Current warehouse"
    field_name = "current_warehouse"


class BoxACFilter(AutocompleteFilter):
    title = "Box"
    field_name = "box"


class RelatedPackageACFilter(AutocompleteFilter):
    title = "Related package"
    field_name = "package"


class ParentCategoryFilter(AutocompleteFilter):
    title = "Parent category"
    field_name = "parent"


class SmartCustomsCommitableFilter(SimpleListFilter):
    title = "Smart customs commitable"
    parameter_name = "smart_customs_enabled"
    CHOICE_YES = "1"
    CHOICE_NO = "0"
    CHOICES = ((CHOICE_YES, "Yes"), (CHOICE_NO, "No"))

    def lookups(self, request, model_admin):
        return self.CHOICES

    def queryset(self, request, queryset):
        conf = Configuration()
        if self.value() == self.CHOICE_YES:
            return conf.filter_customs_commitable_shipments(queryset)
        elif self.value() == self.CHOICE_NO:
            return conf.filter_customs_non_commitable_shipments(queryset)
        return queryset


class ShipmentTransportFilter(AutocompleteFilter):
    title = "transportation"
    rel_model = models.Box
    field_name = "transportation"
    parameter_name = "box__transportation"
