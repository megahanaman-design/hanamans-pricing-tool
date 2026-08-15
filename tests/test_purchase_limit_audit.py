from pricing_core import Settings, calculate_metrics, max_purchase_yen_for_selling_total

from purchase_limit_audit_helper import AuditScenario, audit_break_even


def test_current_waterfall_and_boundary_are_unchanged():
    result = max_purchase_yen_for_selling_total(117.99, Settings(), 155)
    metrics = calculate_metrics(result.product_price_usd, result.max_purchase_yen, Settings(), 155)

    assert (result.product_price_usd, result.duty_shipping_usd, result.selling_price_usd) == (
        99.99,
        18.0,
        117.99,
    )
    assert result.max_purchase_yen == 8858
    assert metrics == {
        "duty_shipping_usd": 18.0,
        "selling_price_usd": 117.99,
        "sales_yen": 18288.45,
        "total_sales_yen": 19751.526,
        "ebay_fvf_yen": 2679.0771950000003,
        "international_fee_yen": 266.645601,
        "ad_fee_yen": 395.03052,
        "payoneer_fee_yen": 298.95393368000003,
        "total_fee_yen": 3639.70724968,
        "shipping_yen": 5790.0,
        "gross_profit_yen": 0.7427503200005958,
        "gross_margin": 4.061308202721367e-05,
        "refund_profit_yen": 1072.9196191830006,
        "refund_margin": 0.05866651461348559,
    }
    assert result.gross_profit_at_next_yen == -0.2572496799994042


def test_audit_scenario_matrix_is_deterministic():
    expected = {
        (155, 3000, "gross"): 8858,
        (159.31, 3000, "gross"): 9188,
        (159.31, 3500, "gross"): 8688,
        (155, 3000, "refund"): 10038,
        (159.31, 3000, "refund"): 10409,
        (159.31, 3500, "refund"): 9859,
    }
    for (exchange_rate, shipping, basis), limit in expected.items():
        actual, at_limit, at_next = audit_break_even(
            AuditScenario(basis, exchange_rate, shipping)
        )
        assert actual == limit
        assert at_limit >= 0
        assert at_next < 0


def test_hypotheticals_do_not_change_production_calculation():
    current_before = max_purchase_yen_for_selling_total(117.99, Settings(), 155)

    no_duty = audit_break_even(
        AuditScenario("gross", 155, 3000, exclude_duty_shipping_cost=True)
    )[0]
    no_tax_uplift = audit_break_even(
        AuditScenario("gross", 155, 3000, exclude_sales_tax_fee_uplift=True)
    )[0]

    assert no_duty == 11648
    assert no_tax_uplift == 9096
    assert max_purchase_yen_for_selling_total(117.99, Settings(), 155) == current_before
