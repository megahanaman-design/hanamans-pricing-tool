from django.urls import path
from . import diagnostics, views

app_name = "profit_web"
urlpatterns = [path("", views.home, name="home"), path("simple/", views.simple_calculator, name="simple"),
    path("monthly/", diagnostics.monthly_with_db_diagnostic, name="monthly"), path("ebay/connect/", views.ebay_connect, name="ebay_connect"),
    path("ebay/callback/", views.ebay_callback, name="ebay_callback"), path("ebay/status/", views.ebay_status, name="ebay_status"),
    path("ebay/sync/", views.ebay_sync, name="ebay_sync")]
