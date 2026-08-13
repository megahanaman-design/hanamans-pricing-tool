from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    default_exchange_rate: float = 155
    auto_exchange_rate: float | None = None
    exchange_source: str = "取得失敗"
    exchange_timestamp: str = ""
    sales_tax_rate: float = 0.08
    package_shipping_yen: float = 3000
    ebay_fvf_rate: float = 0.1325
    ebay_fixed_fee_usd: float = 0.40
    international_fee_rate: float = 0.0135
    ad_rate: float = 0.02
    payoneer_fee_rate: float = 0.02
    other_cost_yen: float = 0
    target_profit_yen: float = 10000
    target_margin_1: float = 0.10
    target_margin_2: float = 0.20
    target_margin: float = 0.20


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
