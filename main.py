from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from calculator import Settings, to_float
from exchange_rate import get_usd_jpy_rate
from excel_writer import INPUT_HEADERS, ensure_template, write_result

try:
    from openpyxl import load_workbook
except ImportError as exc:
    raise SystemExit("openpyxl が見つかりません。Python環境に openpyxl をインストールしてから再実行してください。") from exc


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
SETTINGS = Settings()
GUI_SETTINGS_PATH = INPUT_DIR / "gui_settings.json"


def main() -> None:
    created = ensure_template(INPUT_DIR)
    if created:
        print("テンプレートを作成しました。入力後に再実行してください。")
        return

    input_rows = load_purchase_prices(INPUT_DIR / "purchase_input.xlsx")
    prices = [row["国内最安値円"] for row in input_rows]
    if not prices:
        print("input/purchase_input.xlsx に国内最安値円を入力してから再実行してください。")
        return

    settings, gui_config = load_gui_settings(SETTINGS)
    fx_info = get_usd_jpy_rate()
    if gui_config.get("manual_exchange_rate") not in (None, ""):
        fx_info["manual_override"] = gui_config["manual_exchange_rate"]
    write_result(
        OUTPUT_DIR / "pricing_result.xlsx",
        input_rows,
        settings,
        fx_info,
    )
    print(f"pricing_result.xlsx を作成しました: {OUTPUT_DIR / 'pricing_result.xlsx'}")


def load_purchase_prices(path: Path) -> list[dict]:
    wb = load_workbook(path, data_only=True)
    ws = wb["入力"]
    header_map = {cell.value: cell.column for cell in ws[1] if cell.value}
    price_header = "国内最安値円" if "国内最安値円" in header_map else "国内価格円"
    required_headers = [price_header, "メモ"]
    missing = [header for header in required_headers if header not in header_map]
    if missing:
        raise ValueError(f"入力 シートに必要な列がありません: {', '.join(missing)}")

    rows: list[dict] = []
    for row_index in range(2, ws.max_row + 1):
        price = to_float(ws.cell(row=row_index, column=header_map[price_header]).value, None)
        memo = str(ws.cell(row=row_index, column=header_map["メモ"]).value or "").strip()
        if price is None:
            continue
        rows.append({"国内最安値円": price, "メモ": memo})
    return rows


def load_gui_settings(defaults: Settings) -> tuple[Settings, dict]:
    if not GUI_SETTINGS_PATH.exists():
        return defaults, {}
    try:
        raw = json.loads(GUI_SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return defaults, {}

    updates = {}
    target_profit = to_float(raw.get("target_profit_yen"), None)
    target_margin_1 = to_float(raw.get("target_margin_1"), None)
    target_margin_2 = to_float(raw.get("target_margin_2"), None)
    target_margin = to_float(raw.get("target_margin"), None)
    ad_rate = to_float(raw.get("ad_rate"), None)
    sales_tax_rate = to_float(raw.get("sales_tax_rate"), None)
    package_shipping_yen = to_float(raw.get("package_shipping_yen"), None)
    ebay_fvf_rate = to_float(raw.get("ebay_fvf_rate"), None)
    international_fee_rate = to_float(raw.get("international_fee_rate"), None)
    manual_exchange_rate = to_float(raw.get("manual_exchange_rate"), None)

    if target_profit is not None:
        updates["target_profit_yen"] = target_profit
    if target_margin_1 is not None:
        updates["target_margin_1"] = target_margin_1
    if target_margin_2 is not None:
        updates["target_margin_2"] = target_margin_2
        updates["target_margin"] = target_margin_2
    elif target_margin is not None:
        updates["target_margin_2"] = target_margin
        updates["target_margin"] = target_margin
    if ad_rate is not None:
        updates["ad_rate"] = ad_rate
    if sales_tax_rate is not None:
        updates["sales_tax_rate"] = sales_tax_rate
    if package_shipping_yen is not None:
        updates["package_shipping_yen"] = package_shipping_yen
    if ebay_fvf_rate is not None:
        updates["ebay_fvf_rate"] = ebay_fvf_rate
    if international_fee_rate is not None:
        updates["international_fee_rate"] = international_fee_rate

    settings = replace(defaults, **updates) if updates else defaults
    config = {
        "target_profit_yen": target_profit,
        "target_margin_1": target_margin_1,
        "target_margin_2": target_margin_2 if target_margin_2 is not None else target_margin,
        "target_margin": target_margin,
        "ad_rate": ad_rate,
        "sales_tax_rate": sales_tax_rate,
        "package_shipping_yen": package_shipping_yen,
        "ebay_fvf_rate": ebay_fvf_rate,
        "international_fee_rate": international_fee_rate,
        "manual_exchange_rate": manual_exchange_rate,
    }
    return settings, config



if __name__ == "__main__":
    main()
