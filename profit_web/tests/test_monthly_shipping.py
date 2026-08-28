from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from profit_web.services import calculate_monthly_line, monthly_default_shipping_yen


class MonthlyShippingTests(SimpleTestCase):
    def make_line(self, *, price, country="ES", override=None):
        return SimpleNamespace(
            item_price=Decimal(str(price)),
            shipping_amount=Decimal("0"),
            sales_tax=Decimal("0"),
            destination_country=country,
            purchase_total_yen=Decimal("10000"),
            shipping_override_yen=override,
        )

    def test_low_price_non_us_defaults_to_2500(self):
        self.assertEqual(monthly_default_shipping_yen("99", "160", "ES"), Decimal("2500"))
        self.assertEqual(monthly_default_shipping_yen("112", "160", "AU"), Decimal("2500"))

    def test_low_price_cutoff_is_inclusive_at_300(self):
        self.assertEqual(monthly_default_shipping_yen("300", "160", "GB"), Decimal("2500"))
        self.assertEqual(monthly_default_shipping_yen("300.01", "160", "ES"), Decimal("3500"))

    def test_us_low_price_keeps_duty_buffer_on_2500_base(self):
        # $165 rounds to the $200 duty band: $200 * 18% * 160 yen + 2,500 yen.
        self.assertEqual(monthly_default_shipping_yen("165", "160", "US"), Decimal("8260"))

    def test_manual_shipping_override_replaces_default(self):
        line = self.make_line(price="112", override=Decimal("0"))
        result = calculate_monthly_line(line, Decimal("160"))
        self.assertEqual(result.cpass_shipping_yen, Decimal("0"))

    def test_monthly_line_uses_2500_default_without_override(self):
        line = self.make_line(price="112")
        result = calculate_monthly_line(line, Decimal("160"))
        self.assertEqual(result.cpass_shipping_yen, Decimal("2500"))
