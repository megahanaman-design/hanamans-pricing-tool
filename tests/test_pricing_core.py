import pytest

from pricing_core import (
    Settings,
    calculate_metrics,
    calculate_metrics_with_buyer_shipping,
    calculate_summary,
    duty_shipping_usd,
    shipping_table_rows,
)


@pytest.mark.parametrize(
    ("price", "purchase", "expected"),
    [
        (99.99, 10000, {
            "duty_shipping_usd": 18.0, "selling_price_usd": 117.99,
            "sales_yen": 18288.45, "ebay_fvf_yen": 2501.313461,
            "international_fee_yen": 266.645601, "ad_fee_yen": 395.03052,
            "payoneer_fee_yen": 302.50920836, "total_fee_yen": 3465.49879036,
            "shipping_yen": 5790.0, "gross_profit_yen": -967.04879036,
            "gross_margin": -0.05287756974265176,
            "refund_profit_yen": 192.47791946350037,
            "refund_margin": 0.010524561647569933,
        }),
        (2499.99, 100000, {
            "duty_shipping_usd": 449.82, "selling_price_usd": 2949.81,
            "gross_profit_yen": 209734.71188316002,
            "gross_margin": 0.45871672190403523,
            "refund_profit_yen": 224103.8629132232,
            "refund_margin": 0.490143898635403,
        }),
        (2500.00, 100000, {
            "duty_shipping_usd": 0, "selling_price_usd": 2500.00,
            "gross_profit_yen": 215336.83,
            "refund_profit_yen": 229448.0407916667,
        }),
    ],
)
def test_golden_metrics(price, purchase, expected):
    actual = calculate_metrics(price, purchase, Settings(), 155)
    for key, value in expected.items():
        assert actual[key] == pytest.approx(value)


def test_fixed_buyer_shipping_uses_exact_policy_charge_for_revenue_and_cost():
    settings = Settings(package_shipping_yen=3500)
    actual = calculate_metrics_with_buyer_shipping(600, 117, 68480, settings, 159.32)

    assert actual["duty_shipping_usd"] == 117
    assert actual["selling_price_usd"] == 717
    assert actual["shipping_yen"] == pytest.approx(3500 + 117 * 159.32)
    assert actual["gross_margin"] == pytest.approx(0.019985831381418503)


def test_fixed_buyer_shipping_rejects_negative_or_nonfinite_values():
    settings = Settings()
    with pytest.raises(ValueError, match="buyer_shipping_usd"):
        calculate_metrics_with_buyer_shipping(100, -1, 10000, settings, 155)
    with pytest.raises(ValueError, match="buyer_shipping_usd"):
        calculate_metrics_with_buyer_shipping(100, float("inf"), 10000, settings, 155)


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


def test_basic_store_ccg_fvf_tier_at_exact_2500_and_one_dollar_over():
    settings = Settings(sales_tax_rate=0, package_shipping_yen=0)
    at_cap = calculate_metrics_with_buyer_shipping(2500, 0, 0, settings, 155)
    over_cap = calculate_metrics_with_buyer_shipping(2501, 0, 0, settings, 155)
    assert at_cap["ebay_fvf_yen"] == pytest.approx((2500 * 0.1235 + 0.40) * 155)
    assert over_cap["ebay_fvf_yen"] == pytest.approx(
        (2500 * 0.1235 + 0.0235 + 0.40) * 155
    )
    # The per-item $2,500 threshold is not an item-price threshold.
    assert over_cap["ebay_fvf_yen"] - at_cap["ebay_fvf_yen"] == pytest.approx(0.0235 * 155)


def test_sales_tax_can_move_ccg_fvf_into_upper_tier():
    settings = Settings(sales_tax_rate=0.08, package_shipping_yen=0)
    # $2,320 before tax; fee base is $2,505.60 after the configured 8% tax.
    metrics = calculate_metrics_with_buyer_shipping(200, 2120, 0, settings, 155)
    expected_fvf_usd = 2500 * 0.1235 + 5.6 * 0.0235 + 0.40
    assert metrics["ebay_fvf_yen"] == pytest.approx(expected_fvf_usd * 155)


def test_custom_first_tier_rate_and_refund_are_consistent():
    settings = Settings(ebay_fvf_rate=0.10, sales_tax_rate=0, package_shipping_yen=0)
    metrics = calculate_metrics_with_buyer_shipping(2501, 0, 0, settings, 155)
    expected_variable_fvf_yen = (2500 * 0.10 + 0.0235) * 155
    assert metrics["ebay_fvf_yen"] == pytest.approx(expected_variable_fvf_yen + 0.40 * 155)
    expected_refund = (
        metrics["gross_profit_yen"]
        + 2501 * 155 * ((2500 * 0.10 + 0.0235) / 2501 + 0.0135) * 1.1 * 0.0909
    )
    assert metrics["refund_profit_yen"] == pytest.approx(expected_refund)
