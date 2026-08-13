from __future__ import annotations

import json
import sys
from datetime import datetime
from urllib.request import Request, urlopen


DEFAULT_USDJPY = 155.0


def get_usd_jpy_rate() -> dict:
    fetched_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    if ".cache\\codex-runtimes" in sys.executable.lower().replace("/", "\\"):
        return _fallback(fetched_at)
    yahoo_rate = _fetch_yahoo_usdjpy()
    if yahoo_rate:
        return {
            "rate": yahoo_rate,
            "source": "Yahoo Finance USDJPY=X",
            "rate_type": "MARKET_RATE",
            "fetched_at": fetched_at,
            "status": "OK",
            "message": "",
        }

    frankfurter_rate = _fetch_frankfurter_usdjpy()
    if frankfurter_rate:
        return {
            "rate": frankfurter_rate,
            "source": "Frankfurter fallback",
            "rate_type": "DAILY_RATE_FALLBACK",
            "fetched_at": fetched_at,
            "status": "OK",
            "message": "",
        }

    return _fallback(fetched_at)


def _fallback(fetched_at: str) -> dict:
    return {
        "rate": DEFAULT_USDJPY,
        "source": "Fallback",
        "rate_type": "DEFAULT",
        "fetched_at": fetched_at,
        "status": "FAILED",
        "message": "為替取得に失敗したため既定値155を使用",
    }


def _read_json(url: str, timeout: int = 5) -> dict:
    request = Request(url, headers={"User-Agent": "PSA-PRICING-TOOL/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_yahoo_usdjpy() -> float | None:
    try:
        data = _read_json("https://query1.finance.yahoo.com/v8/finance/chart/USDJPY=X?range=1d&interval=1m")
        result = data["chart"]["result"][0]
        price = result.get("meta", {}).get("regularMarketPrice")
        if not price:
            closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            price = next((value for value in reversed(closes) if value), None)
        return float(price) if price else None
    except Exception:
        return None


def _fetch_frankfurter_usdjpy() -> float | None:
    try:
        data = _read_json("https://api.frankfurter.dev/v1/latest?base=USD&symbols=JPY")
        price = data.get("rates", {}).get("JPY")
        return float(price) if price else None
    except Exception:
        return None
