import secrets
import os
from datetime import datetime, timedelta
from decimal import Decimal

from django.core import signing
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from exchange_rate import get_usd_jpy_rate
from . import ebay
from .forms import SimpleCalculatorForm
from .models import EbayConnection, EbayOrderLine, MonthlyExchangeRate
from .services import calculate_monthly_line, calculate_profit, monthly_default_shipping_yen


def home(request):
    return render(request, "profit_web/home.html")


def privacy(request):
    return render(request, "profit_web/privacy.html")


def simple_calculator(request):
    form = SimpleCalculatorForm(request.POST or None)
    result = calculate_profit(**form.cleaned_data) if request.method == "POST" and form.is_valid() else None
    return render(request, "profit_web/simple_calculator.html", {"form": form, "result": result})


def _month(value):
    try:
        return datetime.strptime(value or "", "%Y-%m").date().replace(day=1)
    except ValueError:
        return timezone.localdate().replace(day=1)


def _rate(month):
    existing = MonthlyExchangeRate.objects.filter(month=month).first()
    if existing:
        return existing
    data = get_usd_jpy_rate()
    fetched = datetime.strptime(data["fetched_at"], "%Y-%m-%d %H:%M:%S")
    return MonthlyExchangeRate.objects.create(month=month, rate=data["rate"], source=data["source"], fetched_at=timezone.make_aware(fetched))


def month_bounds(month, now=None):
    """Return Tokyo-month boundaries, capped at now for the current month."""
    zone = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(month, datetime.min.time()), zone)
    next_month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    end = timezone.make_aware(datetime.combine(next_month, datetime.min.time()), zone)
    current = now or timezone.now()
    if start <= current < end:
        end = current
    return start, end, next_month


def monthly(request):
    month = _month(request.GET.get("month") or request.POST.get("month"))
    if request.method == "POST" and request.POST.get("action") == "save":
        line = EbayOrderLine.objects.get(pk=request.POST["line_id"])
        purchase_value = request.POST.get("purchase_total_yen", "").strip()
        shipping_value = request.POST.get("shipping_override_yen", "").strip()
        line.purchase_total_yen = Decimal(purchase_value) if purchase_value else None
        line.shipping_override_yen = Decimal(shipping_value) if shipping_value else None
        line.save(update_fields=["purchase_total_yen", "shipping_override_yen"])
        return redirect(f"/monthly/?month={month:%Y-%m}")
    rate = _rate(month)
    start_at, end_at, next_month = month_bounds(month)
    lines = list(EbayOrderLine.objects.filter(sold_at__gte=start_at, sold_at__lt=end_at))
    totals = {key: Decimal("0") for key in ("revenue", "purchase", "fvf", "international", "ad", "cpass", "gross", "refund", "with_refund")}
    included = 0
    for line in lines:
        line.default_shipping_yen = monthly_default_shipping_yen(line.item_price, rate.rate, line.destination_country)
        line.shipping_input_yen = line.shipping_override_yen if line.shipping_override_yen is not None else line.default_shipping_yen
        line.shipping_is_manual = line.shipping_override_yen is not None
        line.result = None
        if line.purchase_total_yen is not None and line.eligible_for_profit:
            try:
                result = line.result = calculate_monthly_line(line, rate.rate)
            except ValueError:
                continue
            included += 1
            for key, attr in {"revenue":"revenue_yen", "purchase":None, "fvf":"ebay_fvf_yen", "international":"international_fee_yen", "ad":"ad_cost_yen", "cpass":"cpass_shipping_yen", "gross":"gross_profit_yen", "refund":"tax_refund_yen", "with_refund":"profit_with_refund_yen"}.items():
                totals[key] += line.purchase_total_yen if attr is None else getattr(result, attr)
    totals["gross_margin"] = totals["gross"] / totals["revenue"] * 100 if totals["revenue"] else Decimal("0")
    totals["refund_margin"] = totals["with_refund"] / totals["revenue"] * 100 if totals["revenue"] else Decimal("0")
    context = {"month": month, "previous": month - timedelta(days=1), "next": next_month, "rate": rate, "lines": lines, "totals": totals,
        "connected": EbayConnection.objects.exists(), "last_sync": EbayOrderLine.objects.aggregate(value=Max("last_synced_at"))["value"],
        "count": len(lines), "entered": sum(x.purchase_total_yen is not None for x in lines), "missing": sum(x.purchase_total_yen is None for x in lines), "included": included,
        "config_errors": ebay.configuration_errors(),
        "ebay_config_status": [
            ("Client ID", bool(os.getenv("EBAY_CLIENT_ID"))),
            ("Client Secret", bool(os.getenv("EBAY_CLIENT_SECRET"))),
            ("RuName", bool(os.getenv("EBAY_RUNAME"))),
        ],
        "sync_error": request.GET.get("sync_error")}
    return render(request, "profit_web/monthly.html", context)


def ebay_connect(request):
    raw = secrets.token_urlsafe(32)
    try:
        response = redirect(ebay.authorization_url(raw))
    except ValueError as exc:
        return render(request, "profit_web/ebay_error.html", {"error": str(exc)}, status=503)
    response.set_cookie("ebay_oauth_state", signing.dumps(raw), max_age=600, httponly=True, samesite="Lax", secure=request.is_secure())
    return response


def ebay_callback(request):
    try:
        expected = signing.loads(request.COOKIES.get("ebay_oauth_state", ""), max_age=600)
    except signing.BadSignature:
        return render(request, "profit_web/ebay_error.html", {"error": "OAuth stateが無効または期限切れです。"}, status=400)
    if not secrets.compare_digest(expected, request.GET.get("state", "")):
        return render(request, "profit_web/ebay_error.html", {"error": "OAuth stateが一致しません。"}, status=400)
    token = ebay.exchange_code(request.GET.get("code", ""))
    EbayConnection.objects.all().delete()
    EbayConnection.objects.create(access_token=token["access_token"], refresh_token=token.get("refresh_token", ""), expires_at=timezone.now() + timedelta(seconds=token.get("expires_in", 7200)))
    response = redirect("profit_web:monthly")
    response.delete_cookie("ebay_oauth_state")
    return response


def ebay_status(request):
    connection = EbayConnection.objects.first()
    return JsonResponse({"connected": bool(connection), "updated_at": connection.updated_at if connection else None})


def ebay_sync(request):
    if request.method != "POST":
        return redirect("profit_web:monthly")
    month = _month(request.POST.get("month")); connection = EbayConnection.objects.first()
    if not connection:
        return redirect(f"/monthly/?month={month:%Y-%m}")
    now = timezone.now()
    start, end, unused = month_bounds(month, now)
    if start < now - timedelta(days=90):
        return redirect(f"/monthly/?month={month:%Y-%m}&sync_error=too_old")
    # A future month retains valid start/end ordering, so compare its start to now explicitly.
    # Equality is also rejected: there is no completed time range to request at that instant.
    if start >= now:
        return redirect(f"/monthly/?month={month:%Y-%m}&sync_error=future")
    try:
        ebay.sync_normalized(list(ebay.normalize_orders(ebay.fetch_orders_for_connection(connection, start, end))))
    except Exception:
        # Existing rows remain intact; transaction protects partial database updates.
        return render(request, "profit_web/ebay_error.html", {"error": "eBay同期に失敗しました。既存データは変更されていません。"}, status=502)
    return redirect(f"/monthly/?month={month:%Y-%m}")
