import math

import pytest

from pricing_core import (
    ProductPricePurchaseLimitResult,
    Settings,
    calculate_metrics,
    calculate_summary,
    max_purchase_yen_for_product_price,
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
    assert result.max_purchase_yen == 9032
    assert result.gross_profit_at_limit >= 0
    assert result.gross_profit_at_next_yen < 0


def test_product_price_purchase_limit_uses_product_price_not_selling_total():
    settings = Settings(package_shipping_yen=3500)
    result = max_purchase_yen_for_product_price(117.99, settings, 159.31)

    assert isinstance(result, ProductPricePurchaseLimitResult)
    assert result.product_price_usd == 117.99
    assert result.duty_shipping_usd == 26.82
    assert result.selling_price_usd == 144.81
    assert result.max_purchase_yen == 10939
    assert result.gross_profit_at_limit == pytest.approx(0.6825332303205869)
    assert result.gross_profit_at_next_yen == pytest.approx(-0.3174667696794131)

    at_limit = calculate_metrics(117.99, result.max_purchase_yen, settings, 159.31)
    at_next = calculate_metrics(117.99, result.max_purchase_yen + 1, settings, 159.31)
    assert result.gross_profit_at_limit == at_limit["gross_profit_yen"] >= 0
    assert result.gross_profit_at_next_yen == at_next["gross_profit_yen"] < 0


def test_old_total_cap_and_new_product_price_have_distinct_semantics():
    old = max_purchase_yen_for_selling_total(117.99, Settings(), 155)
    new = max_purchase_yen_for_product_price(117.99, Settings(), 155)

    assert old.product_price_usd == 99.99
    assert old.selling_price_usd == 117.99
    assert old.max_purchase_yen == 9032
    assert new.product_price_usd == 117.99
    assert new.selling_price_usd == 144.81
    assert new.max_purchase_yen == 11049


def test_gui_candidate_break_even_remains_consistent_with_product_price_api():
    settings = Settings(package_shipping_yen=3500)
    below = calculate_metrics(113.99, 10500, settings, 159.31)
    at_break_even = calculate_metrics(114.99, 10500, settings, 159.31)
    summary = calculate_summary(10500, settings, {"rate": 159.31, "source": "test"})

    assert below["gross_profit_yen"] < 0
    assert at_break_even["gross_profit_yen"] >= 0
    assert summary.gross_break_even.product_price_usd == 114.99
    assert summary.gross_break_even.duty_shipping_usd == 26.82
    assert summary.gross_break_even.selling_price_usd == 141.81
    # Existing GUI ceil formatting displays these values as $115 / $27 / $142.
    assert tuple(
        math.ceil(value)
        for value in (
            summary.gross_break_even.product_price_usd,
            summary.gross_break_even.duty_shipping_usd,
            summary.gross_break_even.selling_price_usd,
        )
    ) == (115, 27, 142)


@pytest.mark.parametrize("product_price", [float("nan"), float("inf"), -0.01])
def test_product_price_purchase_limit_rejects_invalid_product_price(product_price):
    with pytest.raises(ValueError):
        max_purchase_yen_for_product_price(product_price, Settings(), 155)


@pytest.mark.parametrize("exchange_rate", [float("nan"), float("inf"), 0, -1])
def test_product_price_purchase_limit_rejects_invalid_exchange_rate(exchange_rate):
    with pytest.raises(ValueError):
        max_purchase_yen_for_product_price(117.99, Settings(), exchange_rate)


def test_zero_product_price_follows_core_no_viable_purchase_policy():
    with pytest.raises(ValueError, match="no non-negative purchase price"):
        max_purchase_yen_for_product_price(0, Settings(), 155)


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
