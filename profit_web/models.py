from django.db import models


class EbayConnection(models.Model):
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class MonthlyExchangeRate(models.Model):
    month = models.DateField(unique=True)
    rate = models.DecimalField(max_digits=12, decimal_places=4)
    source = models.CharField(max_length=100)
    fetched_at = models.DateTimeField()


class EbayOrderLine(models.Model):
    order_id = models.CharField(max_length=100)
    line_item_id = models.CharField(max_length=100)
    legacy_item_id = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=500, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    sold_at = models.DateTimeField()
    item_price = models.DecimalField(max_digits=14, decimal_places=2)
    shipping_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sales_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="USD")
    destination_country = models.CharField(max_length=2, blank=True)
    order_status = models.CharField(max_length=80, blank=True)
    cancellation_status = models.CharField(max_length=80, blank=True)
    refund_status = models.CharField(max_length=40, blank=True)
    purchase_total_yen = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True)
    last_synced_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["order_id", "line_item_id"], name="unique_ebay_order_line")]
        ordering = ["-sold_at", "order_id", "line_item_id"]

    @property
    def excluded(self):
        return self.cancellation_status.lower() not in ("", "not_cancelled", "notrequested") or self.refund_status == "FULL"
