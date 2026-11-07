"""Write bridge contract: authenticated, month-scoped, no raw order IDs."""
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.urls import reverse

from profit_web.models import EbayConnection, EbayOrderLine
from profit_web.sku_master_readonly import _line_key


class MonthlyWriteBridgeTests(TestCase):
    def setUp(self):
        self.token = "w" * 48
        self.month = "2026-11"
        self.sold_at = datetime(2026, 11, 3, tzinfo=ZoneInfo("Asia/Tokyo"))
        self.line = EbayOrderLine.objects.create(
            order_id="private-order-1", line_item_id="private-line-1",
            legacy_item_id="123456789012", title="PSA 10 Pikachu 208/S-P",
            quantity=1, sold_at=self.sold_at, item_price=Decimal("200"),
            last_synced_at=self.sold_at,
        )

    def post(self, name, data, token=None):
        return self.client.post(
            reverse("profit_web:" + name),
            data=__import__("json").dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer " + (token if token is not None else self.token),
        )

    def test_write_token_separate_from_read(self):
        data = {"month": self.month, "line_key": _line_key(self.line),
                "purchase_total_yen": "12000", "shipping_override_yen": "2000"}
        with patch.dict("os.environ", {"SKU_MASTER_MONTHLY_READ_TOKEN": self.token}, clear=True):
            self.assertEqual(self.post("sku_master_monthly_update", data).status_code, 403)
        self.line.refresh_from_db()
        self.assertIsNone(self.line.purchase_total_yen)

    def test_edit_costs_and_clear_manual_shipping(self):
        data = {"month": self.month, "line_key": _line_key(self.line),
                "purchase_total_yen": "12000", "shipping_override_yen": "2500"}
        with patch.dict("os.environ", {"SKU_MASTER_MONTHLY_WRITE_TOKEN": self.token}):
            self.assertEqual(self.post("sku_master_monthly_update", data).status_code, 200)
            data["shipping_override_yen"] = ""
            self.assertEqual(self.post("sku_master_monthly_update", data).status_code, 200)
        self.line.refresh_from_db()
        self.assertEqual(self.line.purchase_total_yen, Decimal("12000"))
        self.assertIsNone(self.line.shipping_override_yen)

    def test_wrong_month_or_amount_never_changes_costs(self):
        data = {"month": "2026-10", "line_key": _line_key(self.line),
                "purchase_total_yen": "12000", "shipping_override_yen": ""}
        with patch.dict("os.environ", {"SKU_MASTER_MONTHLY_WRITE_TOKEN": self.token}):
            self.assertEqual(self.post("sku_master_monthly_update", data).status_code, 404)
            data["month"] = self.month
            data["purchase_total_yen"] = "-1"
            self.assertEqual(self.post("sku_master_monthly_update", data).status_code, 400)
            data["purchase_total_yen"] = "1e9"
            self.assertEqual(self.post("sku_master_monthly_update", data).status_code, 400)
        self.line.refresh_from_db()
        self.assertIsNone(self.line.purchase_total_yen)

    def test_sync_calls_original_ebay_pipeline_once(self):
        EbayConnection.objects.create(access_token="dummy", refresh_token="dummy")
        with (
            patch.dict("os.environ", {"SKU_MASTER_MONTHLY_WRITE_TOKEN": self.token}),
            patch("profit_web.sku_master_write.timezone.now", return_value=datetime(2026, 11, 7, tzinfo=ZoneInfo("Asia/Tokyo"))),
            patch("profit_web.sku_master_write.ebay.fetch_orders_for_connection", return_value=[]) as fetch,
            patch("profit_web.sku_master_write.ebay.normalize_orders", return_value=[]),
            patch("profit_web.sku_master_write.ebay.sync_normalized") as sync,
        ):
            response = self.post("sku_master_monthly_sync", {"month": self.month})
        self.assertEqual(response.status_code, 200)
        fetch.assert_called_once()
        sync.assert_called_once_with([])

    def test_non_auth_sync_does_not_call_ebay(self):
        with patch("profit_web.sku_master_write.ebay.fetch_orders_for_connection") as fetch:
            response = self.post("sku_master_monthly_sync", {"month": self.month})
        self.assertEqual(response.status_code, 403)
        fetch.assert_not_called()
