from decimal import Decimal
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import unquote
from zoneinfo import ZoneInfo
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from .ebay import ebay_timestamp, fetch_orders, fetch_orders_for_connection, get_valid_access_token, normalize_orders, sync_normalized
from .models import EbayConnection, EbayOrderLine, MonthlyExchangeRate
from .services import calculate_monthly_line, calculate_profit, estimate_cpass_shipping, shipping_region
from .views import month_bounds


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
    def payload(self, line_count=1, payment="PAID", cancel="NONE_REQUESTED", order_refunds=None, line_refunds=None):
        return [{"orderId": "ORDER-1", "creationDate": "2026-08-12T10:00:00.000Z",
            "orderFulfillmentStatus": "NOT_STARTED", "cancelStatus": {"cancelState": cancel},
            "orderPaymentStatus": payment,
            "paymentSummary": {"payments": [{"paymentStatus": "SUCCEEDED"}], "refunds": order_refunds or []},
            "pricingSummary": {"deliveryCost": {"value": "10"}, "tax": {"value": "8"}},
            "fulfillmentStartInstructions": [{"shippingStep": {"shipTo": {"contactAddress": {"countryCode": "US"}}}}],
            "lineItems": [{"lineItemId": f"LINE-{n}", "legacyItemId": str(n), "title": f"Card {n}", "quantity": 1, "refunds": line_refunds or [],
                "deliveryCost": {"shippingCost": {"value": str(2 + n), "currency": "USD"}},
                "lineItemCost": {"value": "100", "currency": "USD"}} for n in range(line_count)]}]

    def test_single_and_multi_line_sync_is_idempotent_and_preserves_purchase(self):
        sync_normalized(list(normalize_orders(self.payload())))
        line = EbayOrderLine.objects.get()
        line.purchase_total_yen = 10000; line.save()
        sync_normalized(list(normalize_orders(self.payload(2))))
        self.assertEqual(EbayOrderLine.objects.count(), 2)
        self.assertEqual(EbayOrderLine.objects.get(line_item_id="LINE-0").purchase_total_yen, 10000)

    def test_adapter_allocates_tax_and_shipping_and_marks_states(self):
        lines = list(normalize_orders(self.payload(2, payment="FULLY_REFUNDED", cancel="CANCELED")))
        self.assertEqual(lines[0]["sales_tax"], Decimal("4.0"))
        self.assertEqual(lines[0]["shipping_amount"], Decimal("2"))
        self.assertEqual(lines[0]["refund_status"], "FULL")

    def test_real_api_states_and_refund_arrays(self):
        normal = list(normalize_orders(self.payload()))[0]
        self.assertEqual(normal["cancellation_status"], "NONE_REQUESTED")
        self.assertEqual(normal["refund_status"], "")
        partial = list(normalize_orders(self.payload(payment="PARTIALLY_REFUNDED")))[0]
        self.assertEqual(partial["refund_status"], "REVIEW")
        line_refund = list(normalize_orders(self.payload(line_refunds=[{"refundId": "R1"}] )))[0]
        self.assertEqual(line_refund["refund_status"], "REVIEW")

    def test_line_shipping_falls_back_to_allocated_order_shipping(self):
        payload = self.payload(2)
        del payload[0]["lineItems"][0]["deliveryCost"]
        lines = list(normalize_orders(payload))
        self.assertEqual(lines[0]["shipping_amount"], Decimal("5.0"))
        self.assertEqual(lines[1]["shipping_amount"], Decimal("3"))

    def test_ebay_timestamp_and_creationdate_filter_are_utc_timestamps(self):
        start = datetime(2026, 8, 1, tzinfo=ZoneInfo("Asia/Tokyo"))
        end = datetime(2026, 8, 28, 9, tzinfo=ZoneInfo("Asia/Tokyo"))
        self.assertEqual(ebay_timestamp(start), "2026-07-31T15:00:00.000Z")
        response = patch("profit_web.ebay.urlopen").start()
        self.addCleanup(patch.stopall)
        response.return_value.__enter__.return_value.read.return_value = b'{"orders": [], "total": 0}'
        fetch_orders("secret", start, end)
        url = unquote(response.call_args.args[0].full_url)
        self.assertIn("creationdate:[2026-07-31T15:00:00.000Z..2026-08-28T00:00:00.000Z]", url)


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

    def test_api_status_and_currency_eligibility(self):
        paid = self.make_line(100, 1000); paid.cancellation_status = "NONE_REQUESTED"
        self.assertTrue(paid.eligible_for_profit)
        paid.cancellation_status = "IN_PROGRESS"; self.assertTrue(paid.needs_review)
        paid.cancellation_status = "CANCELED"; self.assertTrue(paid.excluded)
        paid.cancellation_status = "NONE_REQUESTED"
        paid.refund_status = "FULL"; self.assertTrue(paid.excluded)
        paid.refund_status = "REVIEW"; self.assertTrue(paid.needs_review)
        paid.refund_status = ""; paid.currency = "EUR"; self.assertTrue(paid.needs_review)

    def test_tokyo_month_bounds_cap_current_month_but_not_past_month(self):
        now = datetime(2026, 8, 28, 12, 34, tzinfo=timezone.utc)
        start, end, unused = month_bounds(datetime(2026, 8, 1).date(), now)
        self.assertEqual(start.astimezone(timezone.utc), datetime(2026, 7, 31, 15, tzinfo=timezone.utc))
        self.assertEqual(end, now)
        past_start, past_end, unused = month_bounds(datetime(2026, 7, 1).date(), now)
        self.assertEqual(past_start.astimezone(timezone.utc), datetime(2026, 6, 30, 15, tzinfo=timezone.utc))
        self.assertEqual(past_end.astimezone(timezone.utc), datetime(2026, 7, 31, 15, tzinfo=timezone.utc))

    @patch("profit_web.views.get_usd_jpy_rate", return_value={"rate": 150, "source": "mock", "fetched_at": "2026-08-01 00:00:00"})
    def test_totals_exclude_missing_cancelled_and_use_weighted_margin(self, unused):
        self.make_line(100, 1000, suffix="1"); self.make_line(300, 2000, suffix="2")
        self.make_line(500, None, suffix="3"); self.make_line(900, 100, suffix="4", cancel="CANCELLED")
        non_usd = self.make_line(700, 100, suffix="5"); non_usd.currency = "EUR"; non_usd.save()
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

    @patch("profit_web.views.ebay.fetch_orders_for_connection", side_effect=OSError("offline"))
    def test_api_error_does_not_destroy_existing_data(self, unused):
        self.make_line(100, 1000); EbayConnection.objects.create(access_token="not-logged")
        response = self.client.post(reverse("profit_web:ebay_sync"), {"month": "2026-08"})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(EbayOrderLine.objects.count(), 1)

    @patch("profit_web.views.ebay.fetch_orders_for_connection")
    @patch("profit_web.views.timezone.now", return_value=datetime(2026, 8, 28, tzinfo=timezone.utc))
    def test_orders_older_than_ninety_days_are_rejected_without_api_or_data_loss(self, unused, fetch):
        self.make_line(100, 1000); EbayConnection.objects.create(access_token="token")
        response = self.client.post(reverse("profit_web:ebay_sync"), {"month": "2026-04"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("sync_error=too_old", response.url)
        fetch.assert_not_called()
        self.assertEqual(EbayOrderLine.objects.count(), 1)

    @patch("profit_web.views.ebay.fetch_orders_for_connection")
    @patch("profit_web.views.timezone.now", return_value=datetime(2026, 8, 28, tzinfo=timezone.utc))
    def test_future_month_is_rejected_without_api_or_data_loss(self, unused, fetch):
        self.make_line(100, 1000); EbayConnection.objects.create(access_token="token")
        response = self.client.post(reverse("profit_web:ebay_sync"), {"month": "2026-09"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("month=2026-09", response.url)
        self.assertIn("sync_error=future", response.url)
        fetch.assert_not_called()
        self.assertEqual(EbayOrderLine.objects.count(), 1)

    @patch("profit_web.views.ebay.sync_normalized")
    @patch("profit_web.views.ebay.fetch_orders_for_connection", return_value=[])
    @patch("profit_web.views.timezone.now", return_value=datetime(2026, 8, 28, tzinfo=timezone.utc))
    def test_current_month_still_syncs(self, unused, fetch, sync):
        EbayConnection.objects.create(access_token="token")
        response = self.client.post(reverse("profit_web:ebay_sync"), {"month": "2026-08"})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("sync_error", response.url)
        fetch.assert_called_once()
        start, end = fetch.call_args.args[1:]
        self.assertLess(start, end)
        self.assertEqual(end, datetime(2026, 8, 28, tzinfo=timezone.utc))
        sync.assert_called_once_with([])


class AccessTokenTests(TestCase):
    def connection(self, expires, refresh="old-refresh"):
        return EbayConnection.objects.create(access_token="old-access", refresh_token=refresh, expires_at=expires)

    @patch("profit_web.ebay.refresh_access_token")
    def test_valid_token_does_not_refresh(self, refresh):
        connection = self.connection(datetime.now(timezone.utc) + timedelta(hours=1))
        self.assertEqual(get_valid_access_token(connection), "old-access")
        refresh.assert_not_called()

    @patch("profit_web.ebay.refresh_access_token", return_value={"access_token": "new-access", "expires_in": 7200})
    def test_expired_token_refreshes_and_preserves_refresh_token(self, refresh):
        connection = self.connection(datetime.now(timezone.utc) - timedelta(seconds=1))
        self.assertEqual(get_valid_access_token(connection), "new-access")
        connection.refresh_from_db()
        self.assertEqual(connection.access_token, "new-access")
        self.assertEqual(connection.refresh_token, "old-refresh")
        refresh.assert_called_once_with("old-refresh")

    @patch("profit_web.ebay.refresh_access_token", return_value={"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 7200})
    def test_refresh_response_can_rotate_refresh_token(self, unused):
        connection = self.connection(datetime.now(timezone.utc) - timedelta(seconds=1))
        get_valid_access_token(connection); connection.refresh_from_db()
        self.assertEqual(connection.refresh_token, "new-refresh")

    @patch("profit_web.ebay.refresh_access_token", side_effect=OSError("refresh unavailable"))
    def test_refresh_failure_does_not_change_existing_orders(self, unused):
        EbayOrderLine.objects.create(order_id="existing", line_item_id="line", sold_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            item_price=100, last_synced_at=datetime.now(timezone.utc))
        connection = self.connection(datetime.now(timezone.utc) - timedelta(seconds=1))
        with self.assertRaises(OSError):
            get_valid_access_token(connection)
        self.assertEqual(EbayOrderLine.objects.count(), 1)
        connection.refresh_from_db()
        self.assertEqual(connection.access_token, "old-access")

    @patch("profit_web.ebay.refresh_access_token", return_value={"access_token": "retry-access", "expires_in": 7200})
    @patch("profit_web.ebay.fetch_orders")
    def test_unauthorized_get_orders_refreshes_and_retries_once(self, fetch, unused):
        fetch.side_effect = [HTTPError("https://api.ebay.com", 401, "Unauthorized", {}, None), []]
        connection = self.connection(datetime.now(timezone.utc) + timedelta(hours=1))
        self.assertEqual(fetch_orders_for_connection(connection, datetime.now(timezone.utc), datetime.now(timezone.utc)), [])
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(fetch.call_args_list[1].args[0], "retry-access")
