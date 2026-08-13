from __future__ import annotations


def shipping_table_rows() -> list[list[object]]:
    rows: list[list[object]] = [[0, "～", 100, 0.18, 18]]
    lower = 100
    while lower <= 2450:
        upper = lower + 49
        rows.append([lower, "～", upper, 0.18, round(upper * 0.18, 2)])
        lower += 50
    return rows


def duty_shipping_usd(product_price_usd: float) -> float:
    if product_price_usd >= 2500:
        return 0
    matched = 0.0
    for row in shipping_table_rows():
        if product_price_usd >= float(row[0]):
            matched = float(row[4])
        else:
            break
    return matched


# Private-name aliases preserve the names used by the original implementation.
_shipping_table_rows = shipping_table_rows
_duty_shipping_usd = duty_shipping_usd
