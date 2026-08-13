from __future__ import annotations

from .calculator import to_float
from .models import Settings


def final_exchange_rate(fx_info: dict, settings: Settings) -> float:
    manual_override = to_float(fx_info.get("manual_override"), None)
    if manual_override is not None:
        return manual_override
    auto_rate = to_float(fx_info.get("rate"), None)
    if auto_rate is not None:
        return auto_rate
    return settings.default_exchange_rate


_final_exchange_rate = final_exchange_rate
