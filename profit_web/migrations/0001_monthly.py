from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(name="EbayConnection", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("access_token", models.TextField()), ("refresh_token", models.TextField(blank=True)), ("expires_at", models.DateTimeField(blank=True, null=True)), ("updated_at", models.DateTimeField(auto_now=True))]),
        migrations.CreateModel(name="MonthlyExchangeRate", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("month", models.DateField(unique=True)), ("rate", models.DecimalField(decimal_places=4, max_digits=12)), ("source", models.CharField(max_length=100)), ("fetched_at", models.DateTimeField())]),
        migrations.CreateModel(name="EbayOrderLine", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("order_id", models.CharField(max_length=100)), ("line_item_id", models.CharField(max_length=100)), ("legacy_item_id", models.CharField(blank=True, max_length=100)), ("title", models.CharField(blank=True, max_length=500)), ("quantity", models.PositiveIntegerField(default=1)), ("sold_at", models.DateTimeField()), ("item_price", models.DecimalField(decimal_places=2, max_digits=14)), ("shipping_amount", models.DecimalField(decimal_places=2, default=0, max_digits=14)), ("sales_tax", models.DecimalField(decimal_places=2, default=0, max_digits=14)), ("currency", models.CharField(default="USD", max_length=8)), ("destination_country", models.CharField(blank=True, max_length=2)), ("order_status", models.CharField(blank=True, max_length=80)), ("cancellation_status", models.CharField(blank=True, max_length=80)), ("refund_status", models.CharField(blank=True, max_length=40)), ("purchase_total_yen", models.DecimalField(blank=True, decimal_places=0, max_digits=14, null=True)), ("last_synced_at", models.DateTimeField())], options={"ordering": ["-sold_at", "order_id", "line_item_id"]}),
        migrations.AddConstraint(model_name="ebayorderline", constraint=models.UniqueConstraint(fields=("order_id", "line_item_id"), name="unique_ebay_order_line")),
    ]
