from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import patch
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from .ebay import normalize_orders, sync_normalized
from .models import EbayConnection, EbayOrderLine, MonthlyExchangeRate
from .services import calculate_monthly_line, calculate_profit, estimate_cpass_shipping, shipping_region


class ShippingTests(SimpleTestCase):
    def test_us_shipping_rounds_up_to_fifty_dollars(self):
        self.assertEqual(estimate_cpass_shipping(199, 155, 3500, "US"), Decimal("9080.00"))

    def test_non_us_shipping_is_fixed(self):
        for country, expected in {"AU": 4500, "GB": 3500, "EU": 3500, "Other": 3500}.items():
            with self.subTest(country=country):
                self.assertEqual(estimate_cpass_shipping(999, 155, 9999, country), Decimal(expected))


class ProfitTests(SimpleTestCase):
    def test_representative_profit_calculation(self):
        result = calculate_profit(sale_price_usd=199, shipping_received_usd=0, country="US",
            purchase_price_yen=10000, domestic_shipping_yen=500, exchange_rate=155,
            ebay_fvf_rate=13.25, international_fee_rate=1.35, ad_rate=2,
            parcel_shipping_yen=3500, sales_tax_rate=8)
        self.assertEqual(result.revenue_yen, Decimal("30845"))
        self.assertEqual(result.fee_base_yen, Decimal("33312.60"))
        self.assertEqual(result.ebay_fvf_yen, Decimal("4413.919500"))
        self.assertEqual(result.gross_profit_yen, Decimal("5784.460400"))
        self.assertEqual(result.profit_with_refund_yen, Decimal("6693.551309090909090909090909"))


class ViewTests(TestCase):
    def test_pages_render(self):
        self.assertContains(self.client.get(reverse("profit_web:home")), "Hanamans Profit Tool")
        self.assertContains(self.client.get(reverse("profit_web:simple")), "簡易利益計算")

    def test_invalid_zero_revenue_is_shown(self):
        data = {"sale_price_usd": 0, "shipping_received_usd": 0, "country": "US",
                "purchase_price_yen": 1000, "domestic_shipping_yen": 0, "exchange_rate": 155,
                "ebay_fvf_rate": 13.25, "international_fee_rate": 1.35, "ad_rate": 2,
                "parcel_shipping_yen": 3500, "sales_tax_rate": 8}
        self.assertContains(self.client.post(reverse("profit_web:simple"), data), "売上円は0より大きい値")


class EbayAdapterTests(TestCase):
    def payload(self, line_count=1, payment="PAID", cancel="NOT_REQUESTED"):
        return [{"orderId": "ORDER-1", "creationDate": "2026-08-12T10:00:00.000Z",
            "orderFulfillmentStatus": "NOT_STARTED", "cancelStatus": {"cancelState": cancel},
            "paymentSummary": {"paymentStatus": payment},
            "pricingSummary": {"deliveryCost": {"value": "10"}, "tax": {"value": "8"}},
            "fulfillmentStartInstructions": [{"shippingStep": {"shipTo": {"contactAddress": {"countryCode": "US"}}}}],
            "lineItems": [{"lineItemId": f"LINE-{n}", "legacyItemId": str(n), "title": f"Card {n}", "quantity": 1,
                "lineItemCost": {"value": "100", "currency": "USD"}} for n in range(line_count)]}]

    def test_single_and_multi_line_sync_is_idempotent_and_preserves_purchase(self):
        sync_normalized(list(normalize_orders(self.payload())))
        line = EbayOrderLine.objects.get()
        line.purchase_total_yen = 10000; line.save()
        sync_normalized(list(normalize_orders(self.payload(2))))
        self.assertEqual(EbayOrderLine.objects.count(), 2)
        self.assertEqual(EbayOrderLine.objects.get(line_item_id="LINE-0").purchase_total_yen, 10000)

    def test_adapter_allocates_tax_and_shipping_and_marks_states(self):
        lines = list(normalize_orders(self.payload(2, payment="FULLY_REFUNDED", cancel="CANCELLED")))
        self.assertEqual(lines[0]["sales_tax"], Decimal("4.0"))
        self.assertEqual(lines[0]["shipping_amount"], Decimal("5.0"))
        self.assertEqual(lines[0]["refund_status"], "FULL")


class MonthlyProfitTests(TestCase):
    def make_line(self, price, purchase, country="US", tax="0", suffix="1", cancel=""):
        return EbayOrderLine.objects.create(order_id="O" + suffix, line_item_id="L" + suffix,
            sold_at=datetime(2026, 8, 10, tzinfo=timezone.utc), item_price=price, shipping_amount=0,
            sales_tax=tax, destination_country=country, purchase_total_yen=purchase,
            cancellation_status=cancel, last_synced_at=datetime.now(timezone.utc))

    def test_country_classification_and_monthly_actual_sales_tax(self):
        for code, region in {"US":"US", "AU":"AU", "GB":"GB", "DE":"EU", "BR":"Other"}.items():
            self.assertEqual(shipping_region(code), region)
        result = calculate_monthly_line(self.make_line(100, 1000, tax="10"), Decimal("150"))
        self.assertEqual(result.fee_base_yen, Decimal("16500"))
        self.assertEqual(result.gross_margin, result.gross_profit_yen / result.revenue_yen * 100)
        self.assertEqual(result.margin_with_refund, result.profit_with_refund_yen / result.revenue_yen * 100)

    @patch("profit_web.views.get_usd_jpy_rate", return_value={"rate": 150, "source": "mock", "fetched_at": "2026-08-01 00:00:00"})
    def test_totals_exclude_missing_cancelled_and_use_weighted_margin(self, unused):
        self.make_line(100, 1000, suffix="1"); self.make_line(300, 2000, suffix="2")
        self.make_line(500, None, suffix="3"); self.make_line(900, 100, suffix="4", cancel="CANCELLED")
        response = self.client.get(reverse("profit_web:monthly") + "?month=2026-08")
        totals = response.context["totals"]
        self.assertEqual(response.context["included"], 2)
        self.assertEqual(totals["gross_margin"], totals["gross"] / totals["revenue"] * 100)
        self.assertEqual(totals["refund_margin"], totals["with_refund"] / totals["revenue"] * 100)

    @patch("profit_web.views.get_usd_jpy_rate", return_value={"rate": 150, "source": "mock", "fetched_at": "2026-08-01 00:00:00"})
    def test_monthly_renders_disconnected(self, unused):
        self.assertContains(self.client.get(reverse("profit_web:monthly") + "?month=2026-08"), "eBayが未接続です")

    def test_oauth_callback_rejects_invalid_state(self):
        self.assertEqual(self.client.get(reverse("profit_web:ebay_callback"), {"state": "bad"}).status_code, 400)

    @patch("profit_web.views.ebay.fetch_orders", side_effect=OSError("offline"))
    def test_api_error_does_not_destroy_existing_data(self, unused):
        self.make_line(100, 1000); EbayConnection.objects.create(access_token="not-logged")
        response = self.client.post(reverse("profit_web:ebay_sync"), {"month": "2026-08"})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(EbayOrderLine.objects.count(), 1)
