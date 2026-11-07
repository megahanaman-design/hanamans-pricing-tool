from django.urls import path
from . import ebay_notifications, sku_master_readonly, sku_master_write, views

app_name = "profit_web"
urlpatterns = [path("api/sku-master/monthly/update/", sku_master_write.update_costs, name="sku_master_monthly_update"), path("api/sku-master/monthly/sync/", sku_master_write.sync_orders, name="sku_master_monthly_sync"), path("api/sku-master/monthly/", sku_master_readonly.sku_master_monthly_read, name="sku_master_monthly_read"), path("", views.simple_calculator, name="home"), path("privacy/", views.privacy, name="privacy"), path("simple/", views.simple_calculator, name="simple"),
    path("monthly/", views.monthly, name="monthly"), path("ebay/connect/", views.ebay_connect, name="ebay_connect"),
    path("ebay/callback/", views.ebay_callback, name="ebay_callback"), path("ebay/status/", views.ebay_status, name="ebay_status"),
    path("ebay/sync/", views.ebay_sync, name="ebay_sync"),
    path("ebay/marketplace-deletion/", ebay_notifications.marketplace_account_deletion, name="ebay_marketplace_deletion")]
