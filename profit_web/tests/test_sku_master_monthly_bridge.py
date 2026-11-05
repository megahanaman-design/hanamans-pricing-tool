from datetime import datetime
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.urls import reverse

from profit_web.models import EbayOrderLine, MonthlyExchangeRate


class SkuMasterReadOnlyBridgeTests(TestCase):
    def setUp(self):
        self.url = reverse("profit_web:sku_master_monthly_read") + "?month=2026-11"
        self.token = "unit-test-only-secret-should-be-at-least-32-characters"
        self.sold = datetime(2026, 11, 3, 10, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        self.line = EbayOrderLine.objects.create(
            order_id="PRIVATE-ORDER-1",
            line_item_id="PRIVATE-LINE-1",
            legacy_item_id="123456789012",
            title="PSA 10 Pikachu 208/S-P Pokemon Japanese",
            quantity=1,
            sold_at=self.sold,
            item_price=Decimal("200"),
            shipping_amount=Decimal("0"),
            sales_tax=Decimal("10"),
            currency="USD",
            destination_country="GB",
            order_status="FULFILLED",
            cancellation_status="NONE_REQUESTED",
            refund_status="",
            purchase_total_yen=Decimal("12000"),
            last_synced_at=self.sold,
        )
        MonthlyExchangeRate.objects.create(
            month=self.sold.date().replace(day=1),
            rate=Decimal("155"),
            source="unit-test",
            fetched_at=self.sold,
        )

    def get(self, token):
        return self.client.get(self.url, HTTP_AUTHORIZATION="Bearer " + token)

    def test_requires_configured_long_secret(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(self.get(self.token).status_code, 403)
        with patch.dict("os.environ", {"SKU_MASTER_MONTHLY_READ_TOKEN": self.token}):
            self.assertEqual(self.get("wrong").status_code, 403)
            self.assertEqual(self.get(self.token).status_code, 200)

    def test_returns_pii_free_order_data_and_original_profit_math(self):
        with patch.dict("os.environ", {"SKU_MASTER_MONTHLY_READ_TOKEN": self.token}):
            response = self.get(self.token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store, private")
        payload = response.json()
        self.assertEqual(payload["line_count"], 1)
        line = payload["lines"][0]
        self.assertEqual(line["ebay_item_id"], "123456789012")
        self.assertEqual(line["item_price"], "200.00")
        self.assertEqual(line["purchase_total_yen"], "12000")
        self.assertTrue(line["eligible_for_profit"])
        self.assertIsNotNone(line["profit"])
        self.assertEqual(payload["included"], 1)
        self.assertEqual(line["line_key"], __import__("hashlib").sha256(
            b"PRIVATE-ORDER-1\x1fPRIVATE-LINE-1"
        ).hexdigest())
        raw = response.content.decode()
        self.assertNotIn("PRIVATE-ORDER-1", raw)
        self.assertNotIn("PRIVATE-LINE-1", raw)
        self.assertNotIn("refresh_token", raw)
        self.assertNotIn("access_token", raw)

    def test_cancelled_rows_are_present_as_excluded_not_counted(self):
        self.line.cancellation_status = "CANCELED"
        self.line.save(update_fields=["cancellation_status"])
        with patch.dict("os.environ", {"SKU_MASTER_MONTHLY_READ_TOKEN": self.token}):
            response = self.get(self.token)
        line = response.json()["lines"][0]
        self.assertTrue(line["excluded"])
        self.assertFalse(line["eligible_for_profit"])
        self.assertIsNone(line["profit"])
        self.assertEqual(response.json()["included"], 0)

    def test_invalid_month_returns_no_rows(self):
        with patch.dict("os.environ", {"SKU_MASTER_MONTHLY_READ_TOKEN": self.token}):
            response = self.client.get(
                reverse("profit_web:sku_master_monthly_read") + "?month=all",
                HTTP_AUTHORIZATION="Bearer " + self.token,
            )
        self.assertEqual(response.status_code, 400)

    def test_tokyo_month_boundary_is_consistent_with_original_monthly_view(self):
        # 2026-10-31 15:15 UTC is already November 1 in Tokyo.
        self.line.sold_at = datetime(2026, 10, 31, 15, 15, tzinfo=ZoneInfo("UTC"))
        self.line.save(update_fields=["sold_at"])
        with patch.dict("os.environ", {"SKU_MASTER_MONTHLY_READ_TOKEN": self.token}):
            response = self.get(self.token)
            october = self.client.get(
                reverse("profit_web:sku_master_monthly_read") + "?month=2026-10",
                HTTP_AUTHORIZATION="Bearer " + self.token,
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["line_count"], 1)
        self.assertTrue(response.json()["lines"][0]["sold_at"].startswith("2026-11-01T00:15"))
        self.assertEqual(october.json()["line_count"], 0)

    def test_missing_exchange_rate_never_creates_financial_data(self):
        MonthlyExchangeRate.objects.all().delete()
        with patch.dict("os.environ", {"SKU_MASTER_MONTHLY_READ_TOKEN": self.token}):
            response = self.get(self.token)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["exchange_rate"])
        self.assertIsNone(data["lines"][0]["profit"])
        self.assertEqual(data["included"], 0)
        self.assertEqual(MonthlyExchangeRate.objects.count(), 0)
        self.assertEqual(EbayOrderLine.objects.count(), 1)
