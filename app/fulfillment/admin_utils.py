from django.contrib import admin
from modeltranslation.admin import TranslationAdmin


class SoftDeletionAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = self.model.all_objects.all()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not (
            obj and obj.deleted_at
        )


class TranslatedSoftDeletionAdmin(TranslationAdmin):
    def get_queryset(self, request):
        qs = self.model.all_objects.all()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not (
            obj and obj.deleted_at
        )


class HardDeletionAdmin(SoftDeletionAdmin):
    def delete_model(self, request, obj):
        obj.hard_delete()

    def delete_queryset(self, request, queryset):
        queryset.hard_delete()


class TranslatedHardDeletionAdmin(TranslatedSoftDeletionAdmin):
    def delete_model(self, request, obj):
        obj.hard_delete()

    def delete_queryset(self, request, queryset):
        queryset.hard_delete()
