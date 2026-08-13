from __future__ import annotations

from collections.abc import Callable

from .calculator import calculate_metrics
from .exchange import final_exchange_rate
from .models import PricePointResult, PricingSummary, Settings, TargetGrossResult


def calculate_summary(domestic_min: float, settings: Settings, fx_info: dict) -> PricingSummary:
    exchange_rate = final_exchange_rate(fx_info, settings)
    candidates = []
    for product_price in (index + 0.99 for index in range(0, 3001)):
        metrics = calculate_metrics(product_price, domestic_min, settings, exchange_rate)
        candidates.append((product_price, metrics))

    gross_break_even = first_price_point(candidates, lambda metrics: metrics["gross_profit_yen"] >= 0)
    refund_break_even = first_price_point(candidates, lambda metrics: metrics["refund_profit_yen"] >= 0)
    target_1 = target_result(candidates, settings.target_margin_1)
    target_2 = target_result(candidates, settings.target_margin_2)
    return PricingSummary(
        used_exchange_rate=exchange_rate,
        exchange_source=str(fx_info.get("source", "Fallback")),
        domestic_min_yen=domestic_min,
        gross_break_even=gross_break_even,
        refund_break_even=refund_break_even,
        target_1=target_1,
        target_2=target_2,
    )


def target_result(candidates: list[tuple[float, dict[str, float]]], target_margin: float) -> TargetGrossResult:
    for product_price, metrics in candidates:
        if metrics["gross_margin"] >= target_margin:
            return TargetGrossResult(target_margin, product_price, metrics["duty_shipping_usd"], metrics["selling_price_usd"], metrics["gross_profit_yen"], metrics["gross_margin"], metrics["refund_profit_yen"], metrics["refund_margin"])
    return TargetGrossResult(target_margin, None, None, None, None, None, None, None)


def first_price_point(
    candidates: list[tuple[float, dict[str, float]]],
    predicate: Callable[[dict[str, float]], bool],
) -> PricePointResult:
    for price, metrics in candidates:
        if predicate(metrics):
            return PricePointResult(price, metrics["duty_shipping_usd"], metrics["selling_price_usd"])
    return PricePointResult(None, None, None)


_target_result = target_result
_first_price_point = first_price_point
