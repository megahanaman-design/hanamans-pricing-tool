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


@dataclass(frozen=True)
class PricePointResult:
    product_price_usd: float | None
    duty_shipping_usd: float | None
    selling_price_usd: float | None


@dataclass(frozen=True)
class TargetGrossResult:
    target_margin: float
    product_price_usd: float | None
    duty_shipping_usd: float | None
    selling_price_usd: float | None
    gross_profit_yen: float | None
    gross_margin: float | None
    refund_profit_yen: float | None
    refund_margin: float | None


@dataclass(frozen=True)
class PricingSummary:
    used_exchange_rate: float
    exchange_source: str
    domestic_min_yen: float
    gross_break_even: PricePointResult
    refund_break_even: PricePointResult
    target_1: TargetGrossResult
    target_2: TargetGrossResult


@dataclass(frozen=True)
class SellingTotalResolution:
    allowed_selling_total_usd: float
    product_price_usd: float
    duty_shipping_usd: float
    selling_price_usd: float


@dataclass(frozen=True)
class MaxPurchaseResult:
    allowed_selling_total_usd: float
    product_price_usd: float
    duty_shipping_usd: float
    selling_price_usd: float
    max_purchase_yen: int
    gross_profit_at_limit: float
    gross_profit_at_next_yen: float
