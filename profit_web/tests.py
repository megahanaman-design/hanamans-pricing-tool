from decimal import Decimal
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from .services import calculate_profit, estimate_cpass_shipping


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
