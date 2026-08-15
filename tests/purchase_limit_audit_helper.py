"""Test-only calculations used by the purchase-limit assumption audit.

This module intentionally calls the production calculator without modifying it.
The two hypothetical switches reproduce the arithmetic locally and must never be
used by the application or purchase-limit API.
"""

from dataclasses import dataclass, replace
import math

from pricing_core import Settings, calculate_metrics, resolve_product_price_for_selling_total


@dataclass(frozen=True)
class AuditScenario:
    basis: str
    exchange_rate: float
    package_shipping_yen: float
    exclude_duty_shipping_cost: bool = False
    exclude_sales_tax_fee_uplift: bool = False


def _profit(purchase_yen: int, scenario: AuditScenario) -> float:
    settings = replace(Settings(), package_shipping_yen=scenario.package_shipping_yen)
    resolved = resolve_product_price_for_selling_total(117.99)
    metrics = calculate_metrics(
        resolved.product_price_usd, purchase_yen, settings, scenario.exchange_rate
    )
    sales_yen = metrics["sales_yen"]

    gross_profit = metrics["gross_profit_yen"]
    if scenario.exclude_duty_shipping_cost:
        gross_profit += resolved.duty_shipping_usd * scenario.exchange_rate

    if scenario.exclude_sales_tax_fee_uplift:
        ebay_fvf = (
            sales_yen * settings.ebay_fvf_rate
            + settings.ebay_fixed_fee_usd * scenario.exchange_rate
        )
        international_fee = sales_yen * settings.international_fee_rate
        ad_fee = sales_yen * settings.ad_rate
        payoneer_fee = (
            sales_yen - ebay_fvf - international_fee - ad_fee
        ) * settings.payoneer_fee_rate
        hypothetical_total_fee = ebay_fvf + international_fee + ad_fee + payoneer_fee
        gross_profit += metrics["total_fee_yen"] - hypothetical_total_fee

    if scenario.basis == "gross":
        return gross_profit
    if scenario.basis != "refund":
        raise ValueError("basis must be 'gross' or 'refund'")

    # This is the canonical refund adjustment from calculate_metrics.  It is
    # applied to the locally adjusted gross profit only for audit hypotheticals.
    return (
        gross_profit
        + purchase_yen * 0.0909
        + sales_yen
        * (settings.ebay_fvf_rate + settings.international_fee_rate)
        * 1.1
        * 0.0909
    )


def audit_break_even(scenario: AuditScenario) -> tuple[int, float, float]:
    """Return the greatest integer purchase with nonnegative selected profit."""
    low, high = 0, 1
    while _profit(high, scenario) >= 0:
        low, high = high, high * 2
    while low + 1 < high:
        middle = (low + high) // 2
        if _profit(middle, scenario) >= 0:
            low = middle
        else:
            high = middle
    assert math.isfinite(_profit(low, scenario))
    return low, _profit(low, scenario), _profit(low + 1, scenario)
