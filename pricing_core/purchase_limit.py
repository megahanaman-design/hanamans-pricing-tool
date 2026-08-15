from __future__ import annotations

import math
from decimal import Decimal, ROUND_FLOOR

from .calculator import calculate_metrics
from .models import (
    MaxPurchaseResult,
    ProductPricePurchaseLimitResult,
    SellingTotalResolution,
    Settings,
)
from .shipping import shipping_table_rows


_CENT = Decimal("0.01")
_DUTY_FREE_THRESHOLD = Decimal("2500.00")


def _decimal_amount(value: float, name: str) -> Decimal:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    amount = Decimal(str(value))
    if amount < 0:
        raise ValueError(f"{name} must be non-negative")
    return amount


def _floor_cents(amount: Decimal) -> Decimal:
    return amount.quantize(_CENT, rounding=ROUND_FLOOR)


def _max_purchase_with_nonnegative_gross(
    product_price_usd: float,
    settings: Settings,
    exchange_rate: float,
) -> tuple[int, float, float]:
    """Find and verify the greatest integer purchase price at gross break-even."""

    def gross_profit(purchase_yen: int) -> float:
        return calculate_metrics(
            product_price_usd, purchase_yen, settings, exchange_rate
        )["gross_profit_yen"]

    if gross_profit(0) < 0:
        raise ValueError("no non-negative purchase price can produce non-negative gross profit")

    low, high = 0, 1
    while gross_profit(high) >= 0:
        low, high = high, high * 2

    while low + 1 < high:
        middle = (low + high) // 2
        if gross_profit(middle) >= 0:
            low = middle
        else:
            high = middle

    profit_at_limit = gross_profit(low)
    profit_at_next = gross_profit(low + 1)
    if profit_at_limit < 0 or profit_at_next >= 0:
        raise RuntimeError("gross-profit purchase limit failed boundary verification")
    return low, profit_at_limit, profit_at_next


def resolve_product_price_for_selling_total(
    allowed_selling_total_usd: float,
) -> SellingTotalResolution:
    """Resolve the greatest cent-denominated product price within a selling-total cap.

    Candidates are evaluated separately in every current duty-shipping price band.
    This deliberately does not assume that selling price is monotonic at $2,500.
    """
    allowed = _decimal_amount(allowed_selling_total_usd, "allowed_selling_total_usd")
    best: tuple[Decimal, Decimal] | None = None
    rows = shipping_table_rows()

    for index, row in enumerate(rows):
        lower = Decimal(str(row[0])).quantize(_CENT)
        next_lower = (
            Decimal(str(rows[index + 1][0]))
            if index + 1 < len(rows)
            else _DUTY_FREE_THRESHOLD
        )
        upper = next_lower - _CENT
        shipping = Decimal(str(row[4])).quantize(_CENT)
        candidate = min(upper, _floor_cents(allowed - shipping))
        if candidate >= lower and (best is None or candidate > best[0]):
            best = candidate, shipping

    # At and beyond $2,500 the current rule makes duty shipping zero.  This
    # separate candidate is essential because selling total drops at the boundary.
    duty_free_candidate = _floor_cents(allowed)
    if duty_free_candidate >= _DUTY_FREE_THRESHOLD and (
        best is None or duty_free_candidate > best[0]
    ):
        best = duty_free_candidate, Decimal("0.00")

    if best is None:
        raise ValueError("allowed_selling_total_usd is below the minimum selling total")

    product_price, shipping = best
    selling_price = product_price + shipping
    return SellingTotalResolution(
        allowed_selling_total_usd=float(allowed),
        product_price_usd=float(product_price),
        duty_shipping_usd=float(shipping),
        selling_price_usd=float(selling_price),
    )


def max_purchase_yen_for_selling_total(
    allowed_selling_total_usd: float,
    settings: Settings,
    exchange_rate: float,
) -> MaxPurchaseResult:
    """Return the greatest integer purchase price whose canonical gross profit is nonnegative."""
    resolved = resolve_product_price_for_selling_total(allowed_selling_total_usd)

    low, profit_at_limit, profit_at_next = _max_purchase_with_nonnegative_gross(
        resolved.product_price_usd, settings, exchange_rate
    )

    return MaxPurchaseResult(
        allowed_selling_total_usd=resolved.allowed_selling_total_usd,
        product_price_usd=resolved.product_price_usd,
        duty_shipping_usd=resolved.duty_shipping_usd,
        selling_price_usd=resolved.selling_price_usd,
        max_purchase_yen=low,
        gross_profit_at_limit=profit_at_limit,
        gross_profit_at_next_yen=profit_at_next,
    )


def max_purchase_yen_for_product_price(
    product_price_usd: float,
    settings: Settings,
    exchange_rate: float,
) -> ProductPricePurchaseLimitResult:
    """Return the gross break-even purchase limit for an eBay product price.

    ``product_price_usd`` excludes duty/shipping. The canonical metrics calculation
    adds duty/shipping to obtain the shipping-included selling total.
    """
    product_price = _decimal_amount(product_price_usd, "product_price_usd")
    exchange = _decimal_amount(exchange_rate, "exchange_rate")
    if exchange == 0:
        raise ValueError("exchange_rate must be positive")

    price = float(product_price)
    metrics = calculate_metrics(price, 0, settings, float(exchange))
    limit, profit_at_limit, profit_at_next = _max_purchase_with_nonnegative_gross(
        price, settings, float(exchange)
    )
    return ProductPricePurchaseLimitResult(
        product_price_usd=price,
        duty_shipping_usd=metrics["duty_shipping_usd"],
        selling_price_usd=metrics["selling_price_usd"],
        max_purchase_yen=limit,
        gross_profit_at_limit=profit_at_limit,
        gross_profit_at_next_yen=profit_at_next,
    )
