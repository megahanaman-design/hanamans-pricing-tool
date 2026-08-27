import base64
import json
import os
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils import timezone

from .models import EbayOrderLine

SCOPE = "https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly"
API_ROOT = "https://api.ebay.com"


def configuration_errors():
    return [name for name in ("EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET", "EBAY_REDIRECT_URI") if not os.getenv(name)]


def authorization_url(state):
    if configuration_errors():
        raise ValueError("不足している環境変数: " + ", ".join(configuration_errors()))
    return "https://auth.ebay.com/oauth2/authorize?" + urlencode({"client_id": os.environ["EBAY_CLIENT_ID"], "redirect_uri": os.environ["EBAY_REDIRECT_URI"], "response_type": "code", "scope": SCOPE, "state": state})


def exchange_code(code):
    credentials = base64.b64encode(f'{os.environ["EBAY_CLIENT_ID"]}:{os.environ["EBAY_CLIENT_SECRET"]}'.encode()).decode()
    body = urlencode({"grant_type": "authorization_code", "code": code, "redirect_uri": os.environ["EBAY_REDIRECT_URI"]}).encode()
    request = Request(API_ROOT + "/identity/v1/oauth2/token", data=body, headers={"Authorization": "Basic " + credentials, "Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def fetch_orders(access_token, start, end):
    # getOrders supports creationdate filtering and pagination. No modifying endpoint exists here.
    offset, orders = 0, []
    while True:
        query = urlencode({"filter": f"creationdate:[{start.isoformat()}..{end.isoformat()}]", "limit": 200, "offset": offset})
        request = Request(API_ROOT + "/sell/fulfillment/v1/order?" + query, headers={"Authorization": "Bearer " + access_token, "Accept": "application/json"}, method="GET")
        with urlopen(request, timeout=30) as response:
            page = json.load(response)
        orders.extend(page.get("orders", []))
        offset += len(page.get("orders", []))
        if offset >= page.get("total", 0) or not page.get("orders"):
            return orders


def _money(obj):
    return Decimal(str((obj or {}).get("value", 0)))


def normalize_orders(orders):
    for order in orders:
        lines = order.get("lineItems") or []
        line_total = sum((_money(x.get("lineItemCost")) for x in lines), Decimal("0"))
        pricing = order.get("pricingSummary") or {}
        shipping = _money(pricing.get("deliveryCost"))
        tax = _money(pricing.get("tax"))
        destination = ((order.get("fulfillmentStartInstructions") or [{}])[0].get("shippingStep") or {}).get("shipTo", {}).get("contactAddress", {}).get("countryCode", "")
        cancel = (order.get("cancelStatus") or {}).get("cancelState", "")
        payment_status = (order.get("paymentSummary") or {}).get("paymentStatus", "")
        for line in lines:
            cost = _money(line.get("lineItemCost"))
            ratio = cost / line_total if line_total else Decimal("0")
            yield {"order_id": order.get("orderId", ""), "line_item_id": line.get("lineItemId", ""),
                "legacy_item_id": line.get("legacyItemId", ""), "title": line.get("title", ""),
                "quantity": line.get("quantity", 1), "sold_at": datetime.fromisoformat(order["creationDate"].replace("Z", "+00:00")),
                "item_price": cost, "shipping_amount": shipping * ratio, "sales_tax": tax * ratio,
                "currency": (line.get("lineItemCost") or {}).get("currency", "USD"), "destination_country": destination,
                "order_status": order.get("orderFulfillmentStatus", ""), "cancellation_status": cancel,
                "refund_status": "FULL" if payment_status == "FULLY_REFUNDED" else ("REVIEW" if payment_status == "PARTIALLY_REFUNDED" else "")}


@transaction.atomic
def sync_normalized(lines):
    now = timezone.now()
    for values in lines:
        key = {"order_id": values.pop("order_id"), "line_item_id": values.pop("line_item_id")}
        EbayOrderLine.objects.update_or_create(**key, defaults={**values, "last_synced_at": now})
