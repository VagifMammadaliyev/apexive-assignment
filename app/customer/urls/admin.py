from django.urls import path

from customer import views

urlpatterns = [
    path("login/", views.AdminLoginView.as_view(), name="admin-auth"),
    path("me/", views.admin_profile_view, name="admin-profile"),
]
