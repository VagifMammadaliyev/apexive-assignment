from django.contrib.admin.sites import AdminSite as OriginalAdminSite

from .forms import AuthFormWithCaptcha


class AdminSite(OriginalAdminSite):
    login_form = AuthFormWithCaptcha
    login_template = "admin/secure_login.html"
    site_header = "Ontime Admin"
    site_title = "Ontime Administration"
    index_title = "Ontime Administration"
