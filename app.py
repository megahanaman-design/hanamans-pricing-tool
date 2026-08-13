from __future__ import annotations

import json
import math
import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from openpyxl import Workbook

from calculator import Settings
from exchange_rate import get_usd_jpy_rate
from excel_writer import write_result
from main import load_gui_settings, load_purchase_prices
from pricing_core import PricePointResult, PricingSummary, TargetGrossResult, calculate_summary


APP_TITLE = "eBay Pricing Tool"
BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
PURCHASE_INPUT = INPUT_DIR / "purchase_input.xlsx"
GUI_SETTINGS = INPUT_DIR / "gui_settings.json"
RESULT_FILE = OUTPUT_DIR / "pricing_result.xlsx"


class PricingApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x700")
        self.minsize(1100, 660)
        self.result_labels: dict[str, tk.StringVar] = {}
        self.info_labels: dict[str, tk.StringVar] = {}
        self.target_result_labels: dict[str, dict[str, tk.StringVar]] = {}
        self._build_ui()
        self._load_existing_settings()

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.configure("Title.TLabel", font=("Yu Gothic UI", 17, "bold"))
        style.configure("ResultTitle.TLabel", font=("Yu Gothic UI", 10, "bold"))
        style.configure("ResultValue.TLabel", font=("Yu Gothic UI", 18, "bold"))
        style.configure("TargetTitle.TLabel", font=("Yu Gothic UI", 12, "bold"))
        style.configure("TargetValue.TLabel", font=("Yu Gothic UI", 13, "bold"))
        style.configure("TargetPrice.TLabel", font=("Yu Gothic UI", 19, "bold"))
        style.configure("TargetStrong.TLabel", font=("Yu Gothic UI", 15, "bold"))
        style.configure("BreakEvenPrice.TLabel", font=("Yu Gothic UI", 14, "bold"))
        style.configure("InfoValue.TLabel", font=("Yu Gothic UI", 10, "bold"))

        root = ttk.Frame(self, padding=16)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        ttk.Label(root, text=APP_TITLE, style="Title.TLabel").grid(row=0, column=0, sticky="w")

        body = ttk.Frame(root)
        body.grid(row=1, column=0, sticky="nsew", pady=(10, 8))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=4)
        body.rowconfigure(0, weight=1)

        self._build_input_area(body)
        self._build_result_area(body)
        self._build_actions(root)

        self.log = tk.StringVar(value="国内最安値円を入力して「計算する」を押してください。")
        ttk.Label(root, textvariable=self.log).grid(row=3, column=0, sticky="ew", pady=(6, 0))

    def _build_input_area(self, parent: ttk.Frame) -> None:
        panel = ttk.LabelFrame(parent, text="入力")
        panel.grid(row=0, column=0, sticky="new", padx=(0, 12))
        panel.columnconfigure(1, weight=1)

        self.domestic_min = tk.StringVar()
        self.target_margin_1 = tk.StringVar(value="10")
        self.target_margin_2 = tk.StringVar(value="20")
        self.ad_rate = tk.StringVar(value="2")
        self.manual_fx = tk.StringVar()
        self.international_fee_rate = tk.StringVar(value="1.35")
        self.sales_tax_rate = tk.StringVar(value="8")
        self.package_shipping_yen = tk.StringVar(value="3000")
        self.ebay_fvf_rate = tk.StringVar(value="13.25")

        basic = ttk.LabelFrame(panel, text="基本入力")
        basic.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 8))
        basic.columnconfigure(1, weight=1)
        basic_rows = [
            ("国内最安値円", self.domestic_min),
            ("目標粗利率1（%）", self.target_margin_1),
            ("目標粗利率2（%）", self.target_margin_2),
            ("広告率（%）", self.ad_rate),
            ("為替手動上書き", self.manual_fx),
        ]
        for row, (label, var) in enumerate(basic_rows):
            ttk.Label(basic, text=label).grid(row=row, column=0, sticky="w", padx=(10, 8), pady=6)
            ttk.Entry(basic, textvariable=var).grid(row=row, column=1, sticky="ew", padx=(0, 10), pady=6)

        details = ttk.LabelFrame(panel, text="詳細設定")
        details.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        details.columnconfigure(1, weight=1)
        detail_rows = [
            ("海外手数料率（%）", self.international_fee_rate),
            ("Sales Tax率（%）", self.sales_tax_rate),
            ("荷物分送料円", self.package_shipping_yen),
            ("eBay FVF率（%）", self.ebay_fvf_rate),
        ]
        for row, (label, var) in enumerate(detail_rows):
            ttk.Label(details, text=label).grid(row=row, column=0, sticky="w", padx=(10, 8), pady=6)
            ttk.Entry(details, textvariable=var).grid(row=row, column=1, sticky="ew", padx=(0, 10), pady=6)

    def _build_result_area(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.columnconfigure(0, weight=1)

        common = ttk.LabelFrame(panel, text="共通情報")
        common.grid(row=0, column=0, sticky="ew")
        for col in range(2):
            common.columnconfigure(col, weight=1)

        self._build_break_even_result(common, "gross_break_even", "粗利ベース損益分岐", 0)
        self._build_break_even_result(common, "refund_break_even", "還付込み損益分岐", 1)

        targets = ttk.Frame(panel)
        targets.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        targets.columnconfigure(0, weight=1)
        targets.columnconfigure(1, weight=1)

        self._build_target_result(targets, "target_1", "目標粗利率1の結果", 0)
        self._build_target_result(targets, "target_2", "目標粗利率2の結果", 1)

        info = ttk.LabelFrame(panel, text="補足情報")
        info.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        info.columnconfigure(1, weight=1)
        info.columnconfigure(3, weight=1)

        info_items = [
            ("used_exchange_rate", "使用為替"),
            ("exchange_source", "為替取得元"),
        ]
        for index, (key, label) in enumerate(info_items):
            row = index // 2
            col = (index % 2) * 2
            ttk.Label(info, text=label).grid(row=row, column=col, sticky="w", padx=(10, 4), pady=6)
            var = tk.StringVar(value="-")
            self.info_labels[key] = var
            ttk.Label(info, textvariable=var, style="InfoValue.TLabel").grid(row=row, column=col + 1, sticky="w", padx=(0, 10), pady=6)

    def _build_break_even_result(self, parent: ttk.Frame, key: str, title: str, column: int) -> None:
        frame = ttk.Frame(parent, padding=8, relief="ridge")
        frame.grid(row=0, column=column, sticky="ew", padx=6, pady=6)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text=title, style="ResultTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        self.result_labels[f"{key}_product_price_usd"] = tk.StringVar(value="-")
        self.result_labels[f"{key}_duty_shipping_usd"] = tk.StringVar(value="-")
        self.result_labels[f"{key}_selling_price_usd"] = tk.StringVar(value="-")
        rows = [
            ("商品価格USD", f"{key}_product_price_usd"),
            ("送料USD", f"{key}_duty_shipping_usd"),
            ("商品価格＋送料USD", f"{key}_selling_price_usd"),
        ]
        for row, (label, var_key) in enumerate(rows, start=1):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=1)
            value_style = "BreakEvenPrice.TLabel" if var_key.endswith("product_price_usd") else "InfoValue.TLabel"
            ttk.Label(frame, textvariable=self.result_labels[var_key], style=value_style).grid(row=row, column=1, sticky="w", padx=(8, 0), pady=1)

    def _build_target_result(self, parent: ttk.Frame, key: str, title: str, column: int) -> None:
        panel = ttk.LabelFrame(parent, text=title)
        panel.grid(row=0, column=column, sticky="new", padx=(0, 8) if column == 0 else (8, 0))
        panel.columnconfigure(1, weight=1)
        self.target_result_labels[key] = {}

        rows = [
            ("target_margin", "目標粗利率"),
            ("product_price_usd", "商品価格USD"),
            ("duty_shipping_usd", "送料USD"),
            ("selling_price_usd", "商品価格＋送料USD"),
            ("gross_profit_yen", "粗利額円"),
            ("gross_margin", "粗利率"),
            ("refund_profit_yen", "還付込み利益額円"),
            ("refund_margin", "還付込み利益率"),
        ]
        for row, (field, label) in enumerate(rows):
            ttk.Label(panel, text=label).grid(row=row, column=0, sticky="w", padx=(10, 8), pady=3)
            var = tk.StringVar(value="-")
            self.target_result_labels[key][field] = var
            value_style = "TargetValue.TLabel"
            if field == "product_price_usd":
                value_style = "TargetPrice.TLabel"
            elif field in {"gross_profit_yen", "refund_profit_yen"}:
                value_style = "TargetStrong.TLabel"
            ttk.Label(panel, textvariable=var, style=value_style).grid(row=row, column=1, sticky="w", padx=(0, 10), pady=3)

    def _build_actions(self, parent: ttk.Frame) -> None:
        actions = ttk.Frame(parent)
        actions.grid(row=2, column=0, sticky="ew")
        for i in range(3):
            actions.columnconfigure(i, weight=1)

        buttons = [
            ("計算する", self.calculate),
            ("入力をクリア", self.clear_inputs),
            ("Settingsを開く", self.open_settings),
        ]
        for index, (label, command) in enumerate(buttons):
            ttk.Button(actions, text=label, command=command).grid(
                row=0,
                column=index,
                sticky="ew",
                padx=3,
                pady=3,
            )

    def _load_existing_settings(self) -> None:
        self.domestic_min.set("")
        self.target_margin_1.set("10")
        self.target_margin_2.set("20")
        self.ad_rate.set("2")
        self.international_fee_rate.set("1.35")
        self.sales_tax_rate.set("8")
        self.package_shipping_yen.set("3000")
        self.ebay_fvf_rate.set("13.25")
        self.manual_fx.set("")

    def calculate(self) -> None:
        try:
            summary = self._run_workflow()
            self._show_summary(summary)
            self.log.set("計算しました。監査用Excelも出力済みです。")
        except Exception as exc:
            self.log.set("エラーが発生しました。")
            messagebox.showerror(APP_TITLE, str(exc))

    def _run_workflow(self) -> PricingSummary:
        domestic_min = self._to_float(self.domestic_min.get())
        if domestic_min is None:
            raise ValueError("国内最安値円を入力してください。")
        self._save_purchase_input(domestic_min)
        self._save_gui_settings()

        settings, gui_config = load_gui_settings(Settings())
        fx_info = get_usd_jpy_rate()
        manual_exchange_rate = gui_config.get("manual_exchange_rate")
        if manual_exchange_rate not in (None, ""):
            fx_info["manual_override"] = manual_exchange_rate

        input_rows = load_purchase_prices(PURCHASE_INPUT)
        write_result(RESULT_FILE, input_rows, settings, fx_info)
        return calculate_summary(input_rows[0]["国内最安値円"], settings, fx_info)

    def _show_summary(self, summary: PricingSummary) -> None:
        self._show_price_point("gross_break_even", summary.gross_break_even)
        self._show_price_point("refund_break_even", summary.refund_break_even)
        self.info_labels["used_exchange_rate"].set(_format_exchange(summary.used_exchange_rate))
        self.info_labels["exchange_source"].set(summary.exchange_source)
        self._show_target_result("target_1", summary.target_1)
        self._show_target_result("target_2", summary.target_2)

    def _show_price_point(self, key: str, result: PricePointResult) -> None:
        self.result_labels[f"{key}_product_price_usd"].set(_format_usd_ceil(result.product_price_usd))
        self.result_labels[f"{key}_duty_shipping_usd"].set(_format_usd_ceil(result.duty_shipping_usd))
        self.result_labels[f"{key}_selling_price_usd"].set(_format_usd_ceil(result.selling_price_usd))

    def _show_target_result(self, key: str, result: TargetGrossResult) -> None:
        labels = self.target_result_labels[key]
        labels["target_margin"].set(_format_percent(result.target_margin))
        labels["product_price_usd"].set(_format_usd_ceil(result.product_price_usd))
        labels["duty_shipping_usd"].set(_format_usd_ceil(result.duty_shipping_usd))
        labels["selling_price_usd"].set(_format_usd_ceil(result.selling_price_usd))
        labels["gross_profit_yen"].set(_format_yen(result.gross_profit_yen))
        labels["gross_margin"].set(_format_percent(result.gross_margin))
        labels["refund_profit_yen"].set(_format_yen(result.refund_profit_yen))
        labels["refund_margin"].set(_format_percent(result.refund_margin))

    def _save_purchase_input(self, domestic_min: float) -> None:
        INPUT_DIR.mkdir(parents=True, exist_ok=True)
        wb = Workbook()
        ws = wb.active
        ws.title = "入力"
        ws.append(["国内最安値円", "メモ"])
        ws.append([domestic_min, ""])
        wb.save(PURCHASE_INPUT)

    def _save_gui_settings(self) -> None:
        INPUT_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "target_margin_1": self._percent_to_decimal(self.target_margin_1.get(), 0.10),
            "target_margin_2": self._percent_to_decimal(self.target_margin_2.get(), 0.20),
            "ad_rate": self._percent_to_decimal(self.ad_rate.get(), 0.02),
            "international_fee_rate": self._percent_to_decimal(self.international_fee_rate.get(), 0.0135),
            "sales_tax_rate": self._percent_to_decimal(self.sales_tax_rate.get(), 0.08),
            "package_shipping_yen": self._to_float(self.package_shipping_yen.get(), 3000),
            "ebay_fvf_rate": self._percent_to_decimal(self.ebay_fvf_rate.get(), 0.1325),
            "manual_exchange_rate": self._to_float(self.manual_fx.get()),
        }
        GUI_SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def open_settings(self) -> None:
        if not RESULT_FILE.exists():
            messagebox.showinfo(APP_TITLE, "先に計算してください。")
            return
        self._open_path(RESULT_FILE)

    def clear_inputs(self) -> None:
        if not messagebox.askokcancel(APP_TITLE, "画面上の入力内容をクリアしますか？"):
            return
        self.domestic_min.set("")
        self.target_margin_1.set("10")
        self.target_margin_2.set("20")
        self.ad_rate.set("2")
        self.international_fee_rate.set("1.35")
        self.sales_tax_rate.set("8")
        self.package_shipping_yen.set("3000")
        self.ebay_fvf_rate.set("13.25")
        self.manual_fx.set("")
        for var in self.result_labels.values():
            var.set("-")
        for group in self.target_result_labels.values():
            for var in group.values():
                var.set("-")
        for var in self.info_labels.values():
            var.set("-")
        self.log.set("入力内容をクリアしました。")

    @staticmethod
    def _to_float(value: str, default: float | None = None) -> float | None:
        value = value.strip().replace(",", "")
        if not value:
            return default
        return float(value)

    def _percent_to_decimal(self, value: str, default: float | None = None) -> float | None:
        number = self._to_float(value.replace("%", ""), None)
        if number is None:
            return default
        return number / 100

    def _open_path(self, path: Path) -> None:
        path = path.resolve()
        if not path.exists():
            messagebox.showinfo(APP_TITLE, f"見つかりません: {path}")
            return
        os.startfile(path)


def _format_usd(value: float | None) -> str:
    return "該当なし" if value is None else f"${value:,.2f}"


def _format_usd_ceil(value: float | None) -> str:
    return "該当なし" if value is None else f"${math.ceil(value):,}"


def _format_yen(value: float | None) -> str:
    return "該当なし" if value is None else f"{value:,.0f}円"


def _format_percent(value: float | None) -> str:
    return "該当なし" if value is None else f"{value:.2%}"


def _format_exchange(value: float | None) -> str:
    return "該当なし" if value is None else f"{value:,.2f}"


if __name__ == "__main__":
    app = PricingApp()
    app.mainloop()
