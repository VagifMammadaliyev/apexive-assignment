from django.contrib import admin
from django.contrib.admin import register as original_register
from django.contrib.auth.models import Group
from core.sites import AdminSite

site = AdminSite()
admin.site = site


def register(*models, site=None):
    return original_register(*models, site=site or admin.site)


admin.register = register
