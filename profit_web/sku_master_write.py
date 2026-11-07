"""Explicit server-to-server writes from the local SKU Master monthly workbench.

Separate write credential; the existing read token NEVER authorizes mutations.
The pricing tool remains the sole owner of orders, costs and profit math.
"""
from __future__ import annotations

import hmac
import json
import os
import re
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import ebay
from .models import EbayConnection, EbayOrderLine
from .sku_master_readonly import _line_key, _month_bounds
from .views import month_bounds


def _error(message, status):
    response = JsonResponse({"error": message}, status=status)
    response["Cache-Control"] = "no-store"
    return response


def _authorized(request):
    configured = os.getenv("SKU_MASTER_MONTHLY_WRITE_TOKEN", "")
    bearer = request.headers.get("Authorization", "")
    return (
        len(configured) >= 32
        and bearer.startswith("Bearer ")
        and hmac.compare_digest(configured, bearer.removeprefix("Bearer "))
    )


def _payload(request):
    if request.content_type != "application/json" or len(request.body) > 4096:
        raise ValueError("invalid_payload")
    data = json.loads(request.body)
    if not isinstance(data, dict):
        raise ValueError("invalid_payload")
    month = data.get("month")
    if not isinstance(month, str):
        raise ValueError("invalid_month")
    try:
        first, start, end = _month_bounds(month)
    except ValueError as exc:
        raise ValueError("invalid_month") from exc
    return data, first, start, end


def _yen(value):
    # Empty clears a manual value. Nonnegative integer yen only, no exponent.
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,9}", value):
        raise ValueError("invalid_yen")
    return Decimal(value)


@csrf_exempt
@require_POST
def update_costs(request):
    if not _authorized(request):
        return _error("not_authorized", 403)
    try:
        data, _month, start, end = _payload(request)
        if set(data) != {"month", "line_key", "purchase_total_yen", "shipping_override_yen"}:
            raise ValueError("invalid_payload")
        key = data["line_key"]
        if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key):
            raise ValueError("invalid_line_key")
        purchase = _yen(data["purchase_total_yen"])
        shipping = _yen(data["shipping_override_yen"])
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return _error(str(exc) if isinstance(exc, ValueError) else "invalid_payload", 400)

    # Resolve the opaque hash ONLY within the requested month. Never accept raw
    # order IDs from the local caller or expose other account information.
    with transaction.atomic():
        lines = list(EbayOrderLine.objects.select_for_update().filter(
            sold_at__gte=start, sold_at__lt=end
        ).order_by("pk")[:2001])
        if len(lines) > 2000:
            return _error("month_too_large", 409)
        matches = [line for line in lines if hmac.compare_digest(_line_key(line), key)]
        if len(matches) != 1:
            return _error("line_not_found", 404)
        line = matches[0]
        line.purchase_total_yen = purchase
        line.shipping_override_yen = shipping
        line.save(update_fields=["purchase_total_yen", "shipping_override_yen"])
    response = JsonResponse({"status": "saved"})
    response["Cache-Control"] = "no-store"
    return response


@csrf_exempt
@require_POST
def sync_orders(request):
    if not _authorized(request):
        return _error("not_authorized", 403)
    try:
        data, month, _start, _end = _payload(request)
        if set(data) != {"month"}:
            return _error("invalid_payload", 400)
    except (ValueError, TypeError, json.JSONDecodeError):
        return _error("invalid_month", 400)
    connection = EbayConnection.objects.first()
    if not connection:
        return _error("ebay_not_connected", 409)
    now = timezone.now()
    start, end, _ = month_bounds(month, now)
    if start < now - timedelta(days=90):
        return _error("too_old", 409)
    if start >= now:
        return _error("future", 409)
    try:
        orders = ebay.fetch_orders_for_connection(connection, start, end)
        ebay.sync_normalized(list(ebay.normalize_orders(orders)))
    except Exception:
        # Never send OAuth credentials or order PII in errors.
        return _error("ebay_sync_failed", 502)
    response = JsonResponse({"status": "synced"})
    response["Cache-Control"] = "no-store"
    return response
