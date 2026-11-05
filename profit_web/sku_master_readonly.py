"""Read-only SKU Master bridge for the existing monthly profit ledger.

No eBay network access, OAuth token transfer, buyer PII or mutable API calls.
The monthly profit ledger remains the sole writer of orders and manual costs.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import EbayOrderLine, MonthlyExchangeRate
from .services import calculate_monthly_line, monthly_default_shipping_yen

TOTAL_KEYS = (
    "revenue", "purchase", "fvf", "international", "ad",
    "cpass", "gross", "refund", "with_refund",
)


def _amount(value):
    return str(value) if value is not None else None


def _month_bounds(text):
    if not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", text):
        raise ValueError("invalid month")
    first = datetime.strptime(text, "%Y-%m")
    end = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    zone = timezone.get_current_timezone()
    return first.date(), timezone.make_aware(first, zone), timezone.make_aware(end, zone)


def _authorized(request):
    configured = os.getenv("SKU_MASTER_MONTHLY_READ_TOKEN", "")
    incoming = request.headers.get("Authorization", "")
    if len(configured) < 32 or not incoming.startswith("Bearer "):
        return False
    return hmac.compare_digest(configured, incoming.removeprefix("Bearer "))


def _line_key(line):
    # Stable across repeated syncs; no raw order IDs leave the profit service.
    return hashlib.sha256(
        f"{line.order_id}\x1f{line.line_item_id}".encode("utf-8")
    ).hexdigest()


@require_GET
def sku_master_monthly_read(request):
    """Authenticated read-only month snapshot, including estimated profit."""
    if not _authorized(request):
        response = JsonResponse({"error": "not_authorized"}, status=403)
        response["Cache-Control"] = "no-store"
        return response
    try:
        month, start, end = _month_bounds(request.GET.get("month", ""))
    except ValueError:
        return JsonResponse({"error": "invalid_month"}, status=400)

    rate = MonthlyExchangeRate.objects.filter(month=month).first()
    rows = list(
        EbayOrderLine.objects.filter(sold_at__gte=start, sold_at__lt=end)
        .order_by("sold_at", "pk")[:2000]
    )
    if len(rows) == 2000:
        return JsonResponse({"error": "month_too_large"}, status=409)

    totals = {key: Decimal("0") for key in TOTAL_KEYS}
    included = 0
    data = []
    for line in rows:
        price = line.item_price
        shipping_estimate = (
            monthly_default_shipping_yen(price, rate.rate, line.destination_country)
            if rate and line.currency.upper() == "USD"
            else None
        )
        shipping_cost = (
            line.shipping_override_yen
            if line.shipping_override_yen is not None else shipping_estimate
        )
        profit = None
        if line.eligible_for_profit and line.purchase_total_yen is not None and rate:
            try:
                result = calculate_monthly_line(line, rate.rate)
            except (ValueError, InvalidOperation):
                pass
            else:
                included += 1
                profit = {
                    "revenue_yen": _amount(result.revenue_yen),
                    "gross_profit_yen": _amount(result.gross_profit_yen),
                    "tax_refund_yen": _amount(result.tax_refund_yen),
                    "profit_with_refund_yen": _amount(result.profit_with_refund_yen),
                    "gross_margin": _amount(result.gross_margin),
                    "margin_with_refund": _amount(result.margin_with_refund),
                }
                for key, value in {
                    "revenue": result.revenue_yen,
                    "purchase": line.purchase_total_yen,
                    "fvf": result.ebay_fvf_yen,
                    "international": result.international_fee_yen,
                    "ad": result.ad_cost_yen,
                    "cpass": result.cpass_shipping_yen,
                    "gross": result.gross_profit_yen,
                    "refund": result.tax_refund_yen,
                    "with_refund": result.profit_with_refund_yen,
                }.items():
                    totals[key] += value

        data.append({
            "line_key": _line_key(line),
            "ebay_item_id": line.legacy_item_id,
            "title": line.title,
            "quantity": line.quantity,
            "sold_at": timezone.localtime(line.sold_at).isoformat(),
            "item_price": _amount(line.item_price),
            "shipping_received": _amount(line.shipping_amount),
            "sales_tax": _amount(line.sales_tax),
            "currency": line.currency,
            "destination_country": line.destination_country,
            "order_status": line.order_status,
            "cancellation_status": line.cancellation_status,
            "refund_status": line.refund_status,
            "excluded": line.excluded,
            "needs_review": line.needs_review,
            "eligible_for_profit": line.eligible_for_profit,
            "purchase_total_yen": _amount(line.purchase_total_yen),
            "shipping_override_yen": _amount(line.shipping_override_yen),
            "shipping_cost_yen": _amount(shipping_cost),
            "last_synced_at": line.last_synced_at.isoformat(),
            "profit": profit,
        })

    denominator = totals["revenue"]
    summary = {key: _amount(value) for key, value in totals.items()}
    summary.update({
        "gross_margin": _amount(totals["gross"] / denominator * 100 if denominator else Decimal("0")),
        "refund_margin": _amount(totals["with_refund"] / denominator * 100 if denominator else Decimal("0")),
    })
    response = JsonResponse({
        "schema_version": 1,
        "source": "hanamans_profit_web",
        "month": month.strftime("%Y-%m"),
        "exchange_rate": (
            {
                "rate": _amount(rate.rate),
                "source": rate.source,
                "fetched_at": rate.fetched_at.isoformat(),
            }
            if rate else None
        ),
        "line_count": len(data),
        "included": included,
        "totals": summary,
        "lines": data,
    })
    response["Cache-Control"] = "no-store, private"
    response["X-Content-Type-Options"] = "nosniff"
    return response
