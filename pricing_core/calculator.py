from __future__ import annotations

import math

from .models import Settings
from .shipping import duty_shipping_usd


def to_float(value, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    if isinstance(value, str):
        value = value.replace(",", "").replace("%", "").strip()
        if not value:
            return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_metrics(
    product_price_usd: float,
    purchase_yen: float,
    settings: Settings,
    exchange_rate: float,
) -> dict[str, float]:
    return calculate_metrics_with_buyer_shipping(
        product_price_usd,
        duty_shipping_usd(product_price_usd),
        purchase_yen,
        settings,
        exchange_rate,
    )


def calculate_metrics_with_buyer_shipping(
    product_price_usd: float,
    buyer_shipping_usd: float,
    purchase_yen: float,
    settings: Settings,
    exchange_rate: float,
) -> dict[str, float]:
    """Calculate canonical metrics with an explicitly fixed buyer shipping charge.

    ``calculate_metrics`` remains the normal Pricing Tool path and derives the
    shipping charge from the product-price table.  This explicit variant is for
    downstream execution contracts that have already selected one eBay Shipping
    Policy and must evaluate Best Offer thresholds against that same fixed charge.
    """
    shipping = float(buyer_shipping_usd)
    if not math.isfinite(shipping) or shipping < 0:
        raise ValueError("buyer_shipping_usd must be non-negative and finite")

    selling_price_usd = product_price_usd + shipping
    sales_yen = selling_price_usd * exchange_rate
    total_sales_yen = sales_yen * (1 + settings.sales_tax_rate)
    # Final value fee is tiered per item on the tax-inclusive selling total.
    # Keep the fixed per-order charge separate from the percentage component.
    fvf_threshold_yen = settings.ebay_fvf_tier_threshold_usd * exchange_rate
    fvf_percentage_yen = (
        min(total_sales_yen, fvf_threshold_yen) * settings.ebay_fvf_rate
        + max(total_sales_yen - fvf_threshold_yen, 0) * settings.ebay_fvf_over_threshold_rate
    )
    ebay_fvf_yen = fvf_percentage_yen + settings.ebay_fixed_fee_usd * exchange_rate
    international_fee_yen = total_sales_yen * settings.international_fee_rate
    ad_fee_yen = total_sales_yen * settings.ad_rate
    payoneer_fee_yen = (
        sales_yen - ebay_fvf_yen - international_fee_yen - ad_fee_yen
    ) * settings.payoneer_fee_rate
    total_fee_yen = ebay_fvf_yen + international_fee_yen + ad_fee_yen + payoneer_fee_yen
    shipping_yen = settings.package_shipping_yen + shipping * exchange_rate
    gross_profit_yen = sales_yen - purchase_yen - total_fee_yen - shipping_yen - settings.other_cost_yen
    gross_margin = gross_profit_yen / sales_yen if sales_yen else 0
    # Preserve the existing refund estimate while applying the effective
    # tier-weighted FVF rate (excluding the non-percentage fixed order fee).
    effective_fvf_rate = (
        fvf_percentage_yen / total_sales_yen if total_sales_yen else settings.ebay_fvf_rate
    )
    refund_profit_yen = (
        gross_profit_yen
        + (purchase_yen * 0.0909)
        + (
            sales_yen
            * (effective_fvf_rate + settings.international_fee_rate)
            * 1.1
            * 0.0909
        )
    )
    refund_margin = refund_profit_yen / sales_yen if sales_yen else 0
    return {
        "duty_shipping_usd": shipping,
        "selling_price_usd": selling_price_usd,
        "sales_yen": sales_yen,
        "total_sales_yen": total_sales_yen,
        "ebay_fvf_yen": ebay_fvf_yen,
        "international_fee_yen": international_fee_yen,
        "ad_fee_yen": ad_fee_yen,
        "payoneer_fee_yen": payoneer_fee_yen,
        "total_fee_yen": total_fee_yen,
        "shipping_yen": shipping_yen,
        "gross_profit_yen": gross_profit_yen,
        "gross_margin": gross_margin,
        "refund_profit_yen": refund_profit_yen,
        "refund_margin": refund_margin,
    }


_calculate_metrics = calculate_metrics
