from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class SimpleCalculatorViewTests(TestCase):
    def test_home_and_compatibility_route_render_defaults_and_results(self):
        for route in ("profit_web:home", "profit_web:simple"):
            response = self.client.get(reverse(route))
            self.assertContains(response, "個別商品 利益計算")
            self.assertContains(response, "粗利ベース損益分岐")
            self.assertContains(response, 'name="target_margin_1" value="5"')
            self.assertContains(response, 'name="target_margin_2" value="10"')
            self.assertContains(response, 'name="package_shipping_yen" value="3500"')
            self.assertContains(response, reverse("profit_web:monthly"))

    @patch("profit_web.views.get_usd_jpy_rate", return_value={"rate": 150, "source": "mock"})
    def test_calculator_returns_break_even_and_both_targets(self, unused):
        response = self.client.post(reverse("profit_web:simple"), {
            "domestic_min_yen": 10000, "target_margin_1": 5, "target_margin_2": 10,
            "ad_rate": 2, "manual_exchange_rate": "", "international_fee_rate": 1.35,
            "sales_tax_rate": 8, "package_shipping_yen": 3500, "ebay_fvf_rate": 13.25,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["result"])
        self.assertContains(response, "5.00%")
        self.assertContains(response, "10.00%")

    def test_clear_button_defines_required_defaults(self):
        response = self.client.get(reverse("profit_web:home"))
        for fragment in ("target_margin_1:'5'", "target_margin_2:'10'", "package_shipping_yen:'3500'", "manual_exchange_rate:''"):
            self.assertContains(response, fragment)
