import pytest

from pricing_core import Settings, calculate_metrics, calculate_summary, duty_shipping_usd, shipping_table_rows


@pytest.mark.parametrize(
    ("price", "purchase", "expected"),
    [
        (99.99, 10000, {
            "duty_shipping_usd": 18.0, "selling_price_usd": 117.99,
            "sales_yen": 18288.45, "ebay_fvf_yen": 2679.077195,
            "international_fee_yen": 266.645601, "ad_fee_yen": 395.03052,
            "payoneer_fee_yen": 298.95393368, "total_fee_yen": 3639.70724968,
            "shipping_yen": 5790.0, "gross_profit_yen": -1141.25724968,
            "gross_margin": -0.06240316974265175,
            "refund_profit_yen": 34.72741918300062,
            "refund_margin": 0.001898871647569948,
        }),
        (2499.99, 100000, {
            "duty_shipping_usd": 449.82, "selling_price_usd": 2949.81,
            "gross_profit_yen": 194962.18880007995,
            "gross_margin": 0.42640731874383153,
            "refund_profit_yen": 210726.94128807695,
            "refund_margin": 0.4608868549064056,
        }),
        (2500.00, 100000, {
            "duty_shipping_usd": 0, "selling_price_usd": 2500.00,
            "gross_profit_yen": 208607.66,
            "refund_profit_yen": 223354.59425,
        }),
    ],
)
def test_golden_metrics(price, purchase, expected):
    actual = calculate_metrics(price, purchase, Settings(), 155)
    for key, value in expected.items():
        assert actual[key] == pytest.approx(value)


def test_shipping_table_and_2500_boundary():
    rows = shipping_table_rows()
    assert rows[0] == [0, "～", 100, 0.18, 18]
    assert rows[-1] == [2450, "～", 2499, 0.18, 449.82]
    assert len(rows) == 49
    assert duty_shipping_usd(2499.99) == 449.82
    assert duty_shipping_usd(2500) == 0


def test_summary_keeps_candidate_range_and_step():
    summary = calculate_summary(10000, Settings(), {"rate": 155, "source": "test"})
    assert summary.used_exchange_rate == 155
    assert summary.exchange_source == "test"
    for result in (summary.gross_break_even, summary.refund_break_even, summary.target_1, summary.target_2):
        assert result.product_price_usd is None or result.product_price_usd % 1 == pytest.approx(0.99)
        assert result.product_price_usd is None or 0.99 <= result.product_price_usd <= 3000.99
