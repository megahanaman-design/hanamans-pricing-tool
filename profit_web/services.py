from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING

HUNDRED = Decimal("100")
EU_COUNTRIES = {"AT", "BE", "BG", "HR", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HU", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK"}


def shipping_region(country_code):
    code = (country_code or "").upper()
    if code in {"US", "AU", "GB"}:
        return code
    return "EU" if code in EU_COUNTRIES else "Other"


@dataclass(frozen=True)
class ProfitResult:
    revenue_yen: Decimal
    fee_base_yen: Decimal
    ebay_fvf_yen: Decimal
    international_fee_yen: Decimal
    ad_cost_yen: Decimal
    cpass_shipping_yen: Decimal
    gross_profit_yen: Decimal
    tax_refund_yen: Decimal
    profit_with_refund_yen: Decimal
    gross_margin: Decimal
    margin_with_refund: Decimal


def estimate_cpass_shipping(sale_price_usd, exchange_rate, parcel_shipping_yen, country):
    sale_price_usd = Decimal(str(sale_price_usd))
    if country == "US":
        price_band = (sale_price_usd / Decimal("50")).to_integral_value(rounding=ROUND_CEILING) * Decimal("50")
        duty_buffer_usd = price_band * Decimal("0.18")
        return Decimal(str(parcel_shipping_yen)) + duty_buffer_usd * Decimal(str(exchange_rate))
    return {"AU": Decimal("4500"), "GB": Decimal("3500"), "EU": Decimal("3500")}.get(country, Decimal("3500"))


def calculate_profit(*, sale_price_usd, shipping_received_usd, country, purchase_price_yen,
                     domestic_shipping_yen, exchange_rate, ebay_fvf_rate,
                     international_fee_rate, ad_rate, parcel_shipping_yen, sales_tax_rate):
    values = {name: Decimal(str(value)) for name, value in locals().items() if name != "country"}
    total_usd = values["sale_price_usd"] + values["shipping_received_usd"]
    revenue = total_usd * values["exchange_rate"]
    if revenue <= 0:
        raise ValueError("売上円は0より大きい必要があります。")
    fee_base = total_usd * (Decimal("1") + values["sales_tax_rate"] / HUNDRED) * values["exchange_rate"]
    fvf = fee_base * values["ebay_fvf_rate"] / HUNDRED
    international = fee_base * values["international_fee_rate"] / HUNDRED
    ad_cost = revenue * values["ad_rate"] / HUNDRED
    cpass = estimate_cpass_shipping(values["sale_price_usd"], values["exchange_rate"], values["parcel_shipping_yen"], country)
    gross = revenue - values["purchase_price_yen"] - values["domestic_shipping_yen"] - fvf - international - ad_cost - cpass
    refund = values["purchase_price_yen"] * Decimal("10") / Decimal("110")
    with_refund = gross + refund
    return ProfitResult(revenue, fee_base, fvf, international, ad_cost, cpass, gross, refund,
                        with_refund, gross / revenue * HUNDRED, with_refund / revenue * HUNDRED)


def calculate_monthly_line(line, exchange_rate):
    """Adapt an API line to the Phase 1 calculator, including actual sales tax."""
    item_price = Decimal(str(line.item_price))
    shipping = Decimal(str(line.shipping_amount))
    sales_tax = Decimal(str(line.sales_tax))
    subtotal = item_price + shipping
    tax_rate = sales_tax / subtotal * HUNDRED if subtotal else Decimal("0")
    return calculate_profit(sale_price_usd=item_price,
        shipping_received_usd=shipping, country=shipping_region(line.destination_country),
        purchase_price_yen=line.purchase_total_yen, domestic_shipping_yen=0,
        exchange_rate=exchange_rate, ebay_fvf_rate=Decimal("13.25"),
        international_fee_rate=Decimal("1.35"), ad_rate=Decimal("2"),
        parcel_shipping_yen=Decimal("3500"), sales_tax_rate=tax_rate)
