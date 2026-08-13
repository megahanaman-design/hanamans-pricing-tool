import pytest

from pricing_core import (
    Settings,
    calculate_metrics,
    max_purchase_yen_for_selling_total,
    resolve_product_price_for_selling_total,
)


@pytest.mark.parametrize(
    ("allowed", "product", "shipping", "selling"),
    [
        (117.99, 99.99, 18.00, 117.99),
        (126.82, 100.00, 26.82, 126.82),
        (2499.99, 2113.17, 386.82, 2499.99),
        (2500.00, 2500.00, 0.00, 2500.00),
        (2500.01, 2500.01, 0.00, 2500.01),
        (2949.81, 2949.81, 0.00, 2949.81),
    ],
)
def test_resolver_evaluates_shipping_bands_and_duty_free_boundary(
    allowed, product, shipping, selling
):
    result = resolve_product_price_for_selling_total(allowed)

    assert result.product_price_usd == product
    assert result.duty_shipping_usd == shipping
    assert result.selling_price_usd == selling
    assert result.selling_price_usd <= allowed

    next_metrics = calculate_metrics(product + 0.01, 0, Settings(), 155)
    assert next_metrics["selling_price_usd"] > allowed


def test_resolver_rejects_total_below_minimum():
    with pytest.raises(ValueError, match="minimum selling total"):
        resolve_product_price_for_selling_total(17.99)


def test_golden_one_purchase_limit_connection():
    result = max_purchase_yen_for_selling_total(117.99, Settings(), 155)

    assert result.product_price_usd == 99.99
    assert result.max_purchase_yen == 8858
    assert result.gross_profit_at_limit >= 0
    assert result.gross_profit_at_next_yen < 0


@pytest.mark.parametrize("allowed", [126.82, 2500.00, 2949.81])
def test_purchase_limit_has_exact_gross_profit_boundary(allowed):
    result = max_purchase_yen_for_selling_total(allowed, Settings(), 155)
    at_limit = calculate_metrics(
        result.product_price_usd, result.max_purchase_yen, Settings(), 155
    )
    at_next = calculate_metrics(
        result.product_price_usd, result.max_purchase_yen + 1, Settings(), 155
    )

    assert result.gross_profit_at_limit == at_limit["gross_profit_yen"]
    assert result.gross_profit_at_next_yen == at_next["gross_profit_yen"]
    assert result.gross_profit_at_limit >= 0
    assert result.gross_profit_at_next_yen < 0
