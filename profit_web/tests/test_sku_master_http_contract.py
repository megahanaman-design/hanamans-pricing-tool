"""Real loopback HTTP contract against a disposable Django test database.

No Vercel secrets, Neon production data, eBay calls or external requests.
"""
import json
import os
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from django.test import LiveServerTestCase

from profit_web.models import EbayOrderLine, MonthlyExchangeRate


class SkuMasterMonthlyHttpContractTests(LiveServerTestCase):
    def setUp(self):
        self.secret = "isolated-bridge-http-unit-token-20261105"
        sold = datetime(2026, 11, 1, 0, 15, tzinfo=ZoneInfo("Asia/Tokyo"))
        EbayOrderLine.objects.create(
            order_id="private-order-isolated",
            line_item_id="private-line-isolated",
            legacy_item_id="123456789012",
            title="PSA 10 Pikachu 208/S-P Pokemon Japanese",
            quantity=1,
            sold_at=sold,
            item_price=Decimal("210.00"),
            shipping_amount=Decimal("0"),
            currency="USD",
            destination_country="GB",
            order_status="FULFILLED",
            purchase_total_yen=Decimal("12500"),
            last_synced_at=sold,
        )
        MonthlyExchangeRate.objects.create(
            month=sold.date().replace(day=1),
            rate=Decimal("155.00"),
            source="isolated-test",
            fetched_at=sold,
        )

    def request(self, token=None, month="2026-11"):
        headers = {"Accept": "application/json"}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        return Request(
            self.live_server_url + "/api/sku-master/monthly/?month=" + month,
            headers=headers,
            method="GET",
        )

    def test_real_http_requires_bearer_and_never_exposes_order_ids(self):
        with patch.dict(os.environ, {"SKU_MASTER_MONTHLY_READ_TOKEN": self.secret}):
            with self.assertRaises(HTTPError) as denied:
                urlopen(self.request(), timeout=5)
            self.assertEqual(denied.exception.code, 403)
            with urlopen(self.request(self.secret), timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers.get("Cache-Control"), "no-store, private")
                body = response.read()
        data = json.loads(body)
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["source"], "hanamans_profit_web")
        self.assertEqual(data["month"], "2026-11")
        self.assertEqual(data["line_count"], 1)
        self.assertEqual(data["included"], 1)
        self.assertEqual(data["lines"][0]["item_price"], "210.00")
        self.assertTrue(data["lines"][0]["sold_at"].startswith("2026-11-01T00:15"))
        self.assertIsNotNone(data["lines"][0]["profit"])
        self.assertNotIn(b"private-order-isolated", body)
        self.assertNotIn(b"private-line-isolated", body)

    def test_http_month_scoping_and_secret_rejection(self):
        with patch.dict(os.environ, {"SKU_MASTER_MONTHLY_READ_TOKEN": self.secret}):
            with self.assertRaises(HTTPError) as denied:
                urlopen(self.request("invalid-secret"), timeout=5)
            self.assertEqual(denied.exception.code, 403)
            with urlopen(self.request(self.secret, month="2026-10"), timeout=5) as response:
                data = json.loads(response.read())
        self.assertEqual(data["line_count"], 0)
        self.assertEqual(data["month"], "2026-10")
        self.assertEqual(data["included"], 0)
