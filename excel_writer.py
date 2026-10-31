from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from calculator import Settings
from pricing_core.shipping import shipping_table_rows


INPUT_HEADERS = ["国内最安値円", "メモ"]
SHIPPING_HEADER_ROW = 33
SHIPPING_FIRST_ROW = 34
SHIPPING_LAST_ROW = 82
CANDIDATE_HEADER_ROW = 87
CANDIDATE_FIRST_ROW = 88
CANDIDATE_LAST_ROW = 3088


def ensure_template(input_dir: Path) -> bool:
    input_dir.mkdir(parents=True, exist_ok=True)
    path = input_dir / "purchase_input.xlsx"
    if path.exists():
        return False
    wb = Workbook()
    ws = wb.active
    ws.title = "入力"
    ws.append(INPUT_HEADERS)
    ws.append(["", ""])
    _format_table_header(ws)
    _set_number_formats(ws, {"A": "#,##0"})
    wb.save(path)
    return True


def write_result(path: Path, input_rows: list[dict], settings: Settings, fx_info: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    sim_ws = wb.active
    sim_ws.title = "Simulator"
    input_ws = wb.create_sheet("InputPrices")
    settings_ws = wb.create_sheet("Settings")

    _build_input_prices_sheet(input_ws, input_rows)
    _build_simulator_sheet(sim_ws)
    _build_settings_sheet(settings_ws, settings, fx_info)

    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    wb.calculation.calcMode = "auto"
    wb.save(path)


def _build_input_prices_sheet(ws, input_rows: list[dict]) -> None:
    ws.append(INPUT_HEADERS)
    for row in input_rows:
        ws.append([row.get("国内最安値円", row.get("国内価格円", "")), row.get("メモ", "")])
    _format_table_header(ws)
    _set_number_formats(ws, {"A": "#,##0"})


def _build_settings_sheet(ws, settings: Settings, fx_info: dict) -> None:
    _build_settings_audit(ws, settings, fx_info)
    _build_fee_breakdown(ws)
    _build_shipping_audit(ws)
    _build_shipping_table(ws)
    _build_candidate_table(ws)
    _fit_columns(ws)
    ws.freeze_panes = "A2"


def _build_settings_audit(ws, settings: Settings, fx_info: dict) -> None:
    _section_title(ws, "A1", "為替情報")
    rows = [
        ("自動取得為替", fx_info.get("rate", settings.default_exchange_rate)),
        ("為替取得元", fx_info.get("source", "Fallback")),
        ("レート種別", fx_info.get("rate_type", "DEFAULT")),
        ("為替取得日時", fx_info.get("fetched_at", "")),
        ("取得ステータス", fx_info.get("status", "FAILED")),
        ("取得メッセージ", fx_info.get("message", "")),
        ("手動上書き為替", fx_info.get("manual_override", "")),
        ("最終使用為替", '=IF(B8<>"",B8,IF(B2<>"",B2,155))'),
    ]
    for row_index, (label, value) in enumerate(rows, start=2):
        ws.cell(row_index, 1, label)
        ws.cell(row_index, 2, value)

    _section_title(ws, "A12", "設定監査")
    audit_rows = [
        ("為替レート", "=B9"),
        ("為替取得元", "=B3"),
        ("為替取得日時", "=B5"),
        ("手動上書き為替", "=B8"),
        ("最終使用為替", "=B9"),
        ("Sales Tax率", settings.sales_tax_rate),
        ("eBay FVF率", settings.ebay_fvf_rate),
        ("eBay固定手数料USD", settings.ebay_fixed_fee_usd),
        ("海外手数料率", settings.international_fee_rate),
        ("広告率", settings.ad_rate),
        ("Payoneer手数料率", settings.payoneer_fee_rate),
        ("荷物分送料円", settings.package_shipping_yen),
        ("その他コスト円", settings.other_cost_yen),
        ("目標粗利率1", settings.target_margin_1),
        ("目標粗利率2", settings.target_margin_2),
    ]
    for row_index, (label, value) in enumerate(audit_rows, start=13):
        ws.cell(row_index, 1, label)
        ws.cell(row_index, 2, value)

    for row in (2, 8, 9, 13, 17):
        ws.cell(row, 2).number_format = "0.00"
    for row in (18, 19, 21, 22, 23, 27, 28):
        ws.cell(row, 2).number_format = "0.00%"
    for row in (20,):
        ws.cell(row, 2).number_format = "$#,##0.00"
    for row in (24, 25, 26):
        ws.cell(row, 2).number_format = "#,##0"

    # Store-category FVF tier inputs are audited separately so existing
    # Simulator cell positions and workbook consumers remain unchanged.
    ws["A29"] = "FVF段階境界USD"
    ws["B29"] = settings.ebay_fvf_tier_threshold_usd
    ws["B29"].number_format = "$#,##0.00"
    ws["A30"] = "FVF境界超過料率"
    ws["B30"] = settings.ebay_fvf_over_threshold_rate
    ws["B30"].number_format = "0.00%"


def _build_fee_breakdown(ws) -> None:
    _section_title(ws, "D1", "手数料内訳")
    rows = [
        ("総販売額円", "=Simulator!$B$22"),
        ("eBay FVF円", "=Simulator!$B$24"),
        ("eBay固定手数料円", "=Simulator!$B$25"),
        ("海外手数料円", "=Simulator!$B$26"),
        ("広告費円", "=Simulator!$B$27"),
        ("Payoneer手数料円", "=Simulator!$B$28"),
        ("合計手数料円", "=Simulator!$B$29"),
    ]
    for row_index, (label, formula) in enumerate(rows, start=2):
        ws.cell(row_index, 4, label)
        ws.cell(row_index, 5, formula)
        ws.cell(row_index, 5).number_format = "#,##0"


def _build_shipping_audit(ws) -> None:
    _section_title(ws, "D11", "送料・関税徴収用送料監査")
    rows = [
        ("荷物分送料円", "=Simulator!$B$7"),
        ("関税徴収用送料USD", "=Simulator!$B$20"),
        ("送料合計円", "=Simulator!$B$30"),
        ("送料テーブル参照範囲", f"Settings!$A${SHIPPING_FIRST_ROW}:$E${SHIPPING_LAST_ROW}"),
        ("2500未満", "送料テーブル参照"),
        ("2500以上", "関税徴収用送料USDは0"),
    ]
    for row_index, (label, value) in enumerate(rows, start=12):
        ws.cell(row_index, 4, label)
        ws.cell(row_index, 5, value)
    ws["E12"].number_format = "#,##0"
    ws["E13"].number_format = "$#,##0.00"
    ws["E14"].number_format = "#,##0"


def _build_shipping_table(ws) -> None:
    _section_title(ws, f"A{SHIPPING_HEADER_ROW - 2}", "送料テーブル")
    headers = ["下限USD", "表示", "上限USD", "関税率", "関税徴収用送料USD"]
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(SHIPPING_HEADER_ROW, col, header)
        _header_cell(cell)

    for index, row in enumerate(_shipping_table_rows(), start=SHIPPING_FIRST_ROW):
        for col, value in enumerate(row, start=1):
            ws.cell(index, col, value)
    _set_number_formats(ws, {"A": "$#,##0.00", "C": "$#,##0.00", "D": "0.00%", "E": "$#,##0.00"})


def _build_candidate_table(ws) -> None:
    _section_title(ws, f"A{CANDIDATE_HEADER_ROW - 2}", "逆算候補テーブル")
    headers = [
        "候補商品価格USD",
        "候補関税徴収用送料USD",
        "候補販売価格USD",
        "候補売上円換算",
        "候補合計手数料円",
        "候補送料合計円",
        "候補粗利額円",
        "候補粗利率",
        "候補還付込み利益額円",
        "候補還付込み利益率",
        "粗利ベース損益分岐フラグ",
        "還付込み損益分岐フラグ",
        "目標粗利率1達成フラグ",
        "目標粗利率2達成フラグ",
    ]
    for col, header in enumerate(headers, start=1):
        _header_cell(ws.cell(CANDIDATE_HEADER_ROW, col, header))

    for row in range(CANDIDATE_FIRST_ROW, CANDIDATE_LAST_ROW + 1):
        ws.cell(row, 1, f"=ROW(A{row - CANDIDATE_FIRST_ROW + 1})-1+0.99")
        ws.cell(row, 2, f'=IF(A{row}<2500,VLOOKUP(A{row},$A${SHIPPING_FIRST_ROW}:$E${SHIPPING_LAST_ROW},5,TRUE),0)')
        ws.cell(row, 3, f"=A{row}+B{row}")
        ws.cell(row, 4, f"=C{row}*Simulator!$B$5")
        ws.cell(row, 5, _candidate_fee_formula(row))
        ws.cell(row, 6, f"=Simulator!$B$7+B{row}*Simulator!$B$5")
        ws.cell(row, 7, f"=D{row}-Simulator!$B$3-E{row}-F{row}-Simulator!$B$13")
        ws.cell(row, 8, f"=IFERROR(G{row}/D{row},0)")
        fee_base = f"(D{row}*(1+Simulator!$B$6))"
        fvf_variable = _tiered_fvf_variable_formula(
            fee_base, "Simulator!$B$8", "Simulator!$B$5"
        )
        ws.cell(
            row, 9,
            f"=G{row}+(Simulator!$B$3*0.0909)"
            f"+(D{row}*({fvf_variable}/{fee_base}+Simulator!$B$10)*1.1*0.0909)",
        )
        ws.cell(row, 10, f"=IFERROR(I{row}/D{row},0)")
        ws.cell(row, 11, f'=IF(G{row}>=0,A{row},"")')
        ws.cell(row, 12, f'=IF(I{row}>=0,A{row},"")')
        ws.cell(row, 13, f'=IF(H{row}>=Simulator!$B$14,A{row},"")')
        ws.cell(row, 14, f'=IF(H{row}>=Simulator!$B$15,A{row},"")')

    _set_number_formats(
        ws,
        {
            "A": "$#,##0.00",
            "B": "$#,##0.00",
            "C": "$#,##0.00",
            "D": "#,##0",
            "E": "#,##0",
            "F": "#,##0",
            "G": "#,##0",
            "H": "0.00%",
            "I": "#,##0",
            "J": "0.00%",
            "K": "$#,##0.00",
            "L": "$#,##0.00",
            "M": "$#,##0.00",
            "N": "$#,##0.00",
        },
    )


def _tiered_fvf_variable_formula(total_sales: str, base_rate: str, exchange_rate: str) -> str:
    cap = f"(Settings!$B$29*{exchange_rate})"
    return (
        f"(MIN({total_sales},{cap})*{base_rate}"
        f"+MAX({total_sales}-{cap},0)*Settings!$B$30)"
    )


def _candidate_fee_formula(row: int) -> str:
    total_sales = f"(D{row}*(1+Simulator!$B$6))"
    variable_fvf = _tiered_fvf_variable_formula(
        total_sales, "Simulator!$B$8", "Simulator!$B$5"
    )
    fvf = f"({variable_fvf}+Simulator!$B$9*Simulator!$B$5)"
    international = f"({total_sales}*Simulator!$B$10)"
    ad = f"({total_sales}*Simulator!$B$11)"
    payoneer = f"((D{row}-{fvf}-{international}-{ad})*Simulator!$B$12)"
    return f"={fvf}+{international}+{ad}+{payoneer}"


def _build_simulator_sheet(ws) -> None:
    input_fill = PatternFill("solid", fgColor="FFF2CC")
    output_fill = PatternFill("solid", fgColor="D9EAF7")
    title_fill = PatternFill("solid", fgColor="1F4E78")
    title_font = Font(color="FFFFFF", bold=True)

    ws["A1"] = "価格シミュレーター"
    ws["A1"].font = Font(size=14, bold=True)

    ws["A2"] = "入力欄"
    ws["A2"].fill = title_fill
    ws["A2"].font = title_font
    ws["A17"] = "出力欄"
    ws["A17"].fill = title_fill
    ws["A17"].font = title_font

    inputs = [
        ("仕入価格円", "=B18"),
        ("商品価格USD", '=IF(B39="該当なし","",B39)'),
        ("為替レート", "=Settings!$B$9"),
        ("Sales Tax率", "=Settings!$B$18"),
        ("荷物分送料円", "=Settings!$B$24"),
        ("eBay FVF率", "=Settings!$B$19"),
        ("eBay固定手数料USD", "=Settings!$B$20"),
        ("海外手数料率", "=Settings!$B$21"),
        ("広告率", "=Settings!$B$22"),
        ("Payoneer手数料率", "=Settings!$B$23"),
        ("その他コスト円", "=Settings!$B$25"),
        ("目標粗利率1", "=Settings!$B$26"),
        ("目標粗利率2", "=Settings!$B$27"),
    ]
    for row, (label, value) in enumerate(inputs, start=3):
        ws.cell(row, 1, label)
        ws.cell(row, 2, value)
        ws.cell(row, 1).fill = input_fill
        ws.cell(row, 2).fill = input_fill

    outputs = [
        ("国内最安値円", "=MIN(InputPrices!A2:A1000)"),
        ("国内平均価格円（未使用）", '=""'),
        ("関税徴収用送料USD", f'=IF($B$4="","",IF($B$4<2500,VLOOKUP($B$4,Settings!$A${SHIPPING_FIRST_ROW}:$E${SHIPPING_LAST_ROW},5,TRUE),0))'),
        ("販売価格USD", '=IF($B$4="","",$B$4+$B$20)'),
        ("総販売額円", '=IF($B$4="","",$B$21*$B$5*(1+$B$6))'),
        ("売上円換算", '=IF($B$4="","",$B$21*$B$5)'),
        (
            "eBay FVF円",
            f'=IF($B$4="","",{_tiered_fvf_variable_formula("$B$22", "$B$8", "$B$5")}+$B$9*$B$5)',
        ),
        ("eBay固定手数料円", '=IF($B$4="","",$B$9*$B$5)'),
        ("海外手数料円", '=IF($B$4="","",$B$22*$B$10)'),
        ("広告費円", '=IF($B$4="","",$B$22*$B$11)'),
        ("Payoneer手数料円", '=IF($B$4="","",($B$23-$B$24-$B$26-$B$27)*$B$12)'),
        ("合計手数料円", '=IF($B$4="","",$B$24+$B$26+$B$27+$B$28)'),
        ("送料合計円", '=IF($B$4="","",$B$7+$B$20*$B$5)'),
        ("粗利額円", '=IF($B$4="","",$B$23-$B$3-$B$29-$B$30-$B$13)'),
        ("粗利率", '=IF($B$4="","",IFERROR($B$31/$B$23,0))'),
        (
            "還付込み利益額円",
            '=IF($B$4="","",$B$31+($B$3*0.0909)'
            '+($B$23*((($B$24-$B$25)/$B$22)+$B$10)*1.1*0.0909))',
        ),
        ("還付込み利益率", '=IF($B$4="","",IFERROR($B$33/$B$23,0))'),
        ("粗利ベース損益分岐商品価格USD", '=IF(COUNT(Settings!$K$88:$K$3088)=0,"該当なし",MIN(Settings!$K$88:$K$3088))'),
        ("還付込み損益分岐商品価格USD", '=IF(COUNT(Settings!$L$88:$L$3088)=0,"該当なし",MIN(Settings!$L$88:$L$3088))'),
        ("目標粗利率1商品価格USD", '=IF(COUNT(Settings!$M$88:$M$3088)=0,"該当なし",MIN(Settings!$M$88:$M$3088))'),
        ("目標粗利率2商品価格USD", '=IF(COUNT(Settings!$N$88:$N$3088)=0,"該当なし",MIN(Settings!$N$88:$N$3088))'),
        ("推奨商品価格USD（目標粗利率2）", "=B38"),
        ("Best Offer下限USD（目標粗利率1）", "=B37"),
    ]
    for row, (label, formula) in enumerate(outputs, start=18):
        ws.cell(row, 1, label)
        ws.cell(row, 2, formula)
        ws.cell(row, 1).fill = output_fill
        ws.cell(row, 2).fill = output_fill

    _build_gui_audit_area(ws)
    _apply_simulator_number_formats(ws)

    for row in range(1, 58):
        for col in range(1, 4):
            ws.cell(row, col).alignment = Alignment(vertical="center")
    ws.freeze_panes = "A3"
    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 18


def _build_gui_audit_area(ws) -> None:
    _section_title(ws, "A43", "GUI照合")
    headers = ["項目", "目標粗利率1", "目標粗利率2"]
    for col, header in enumerate(headers, start=1):
        _header_cell(ws.cell(44, col, header))

    rows = [
        ("商品価格USD", "=B37", "=B38"),
        ("送料USD", '=IF(B45="該当なし","",IF(B45<2500,VLOOKUP(B45,Settings!$A$34:$E$82,5,TRUE),0))', '=IF(C45="該当なし","",IF(C45<2500,VLOOKUP(C45,Settings!$A$34:$E$82,5,TRUE),0))'),
        ("商品価格＋送料USD", '=IF(B45="","",B45+B46)', '=IF(C45="","",C45+C46)'),
        ("売上円換算", '=IF(B45="","",B47*$B$5)', '=IF(C45="","",C47*$B$5)'),
        ("総販売額円", '=IF(B45="","",B47*$B$5*(1+$B$6))', '=IF(C45="","",C47*$B$5*(1+$B$6))'),
        ("合計手数料円", _gui_audit_fee_formula("B"), _gui_audit_fee_formula("C")),
        ("送料合計円", '=IF(B45="","",$B$7+B46*$B$5)', '=IF(C45="","",$B$7+C46*$B$5)'),
        ("粗利額円", '=IF(B45="","",B48-$B$3-B50-B51-$B$13)', '=IF(C45="","",C48-$B$3-C50-C51-$B$13)'),
        ("粗利率", '=IF(B45="","",IFERROR(B52/B48,0))', '=IF(C45="","",IFERROR(C52/C48,0))'),
        (
            "還付込み利益額円",
            _gui_audit_refund_formula("B"),
            _gui_audit_refund_formula("C"),
        ),
        ("還付込み利益率", '=IF(B45="","",IFERROR(B54/B48,0))', '=IF(C45="","",IFERROR(C54/C48,0))'),
    ]
    for row_index, (label, formula_1, formula_2) in enumerate(rows, start=45):
        ws.cell(row_index, 1, label)
        ws.cell(row_index, 2, formula_1)
        ws.cell(row_index, 3, formula_2)


def _gui_audit_fee_formula(column: str) -> str:
    total_sales = f"{column}49"
    sales = f"{column}48"
    variable_fvf = _tiered_fvf_variable_formula(total_sales, "$B$8", "$B$5")
    fvf = f"({variable_fvf}+$B$9*$B$5)"
    international = f"({total_sales}*$B$10)"
    ad = f"({total_sales}*$B$11)"
    payoneer = f"(({sales}-{fvf}-{international}-{ad})*$B$12)"
    return f'=IF({column}45="","",{fvf}+{international}+{ad}+{payoneer})'


def _gui_audit_refund_formula(column: str) -> str:
    variable_fvf = _tiered_fvf_variable_formula(f"{column}49", "$B$8", "$B$5")
    return (
        f'=IF({column}45="","",{column}52+($B$3*0.0909)'
        f'+({column}48*({variable_fvf}/{column}49+$B$10)*1.1*0.0909))'
    )


def _shipping_table_rows() -> list[list[object]]:
    return shipping_table_rows()


def _apply_simulator_number_formats(ws) -> None:
    yen_rows = (3, 7, 13, 18, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 33)
    usd_rows = (4, 9, 20, 21, 35, 36, 37, 38, 39, 40)
    percent_rows = (6, 8, 10, 11, 12, 14, 15, 32, 34)
    for row in yen_rows:
        ws.cell(row, 2).number_format = "#,##0"
    for row in usd_rows:
        ws.cell(row, 2).number_format = "$#,##0.00"
    for row in percent_rows:
        ws.cell(row, 2).number_format = "0.00%"
    ws.cell(5, 2).number_format = "0.00"
    for column in (2, 3):
        for row in (45, 46, 47):
            ws.cell(row, column).number_format = "$#,##0.00"
        for row in (48, 49, 50, 51, 52, 54):
            ws.cell(row, column).number_format = "#,##0"
        for row in (53, 55):
            ws.cell(row, column).number_format = "0.00%"


def _section_title(ws, cell_ref: str, title: str) -> None:
    cell = ws[cell_ref]
    cell.value = title
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="1F4E78")


def _header_cell(cell) -> None:
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="1F4E78")
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _format_table_header(ws) -> None:
    for cell in ws[1]:
        _header_cell(cell)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    _fit_columns(ws)


def _fit_columns(ws) -> None:
    for column_cells in ws.columns:
        letter = get_column_letter(column_cells[0].column)
        max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells[:120])
        ws.column_dimensions[letter].width = min(max(max_len + 2, 12), 42)
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)


def _set_number_formats(ws, formats: dict[str, str]) -> None:
    for column, number_format in formats.items():
        for cell in ws[column][1:]:
            cell.number_format = number_format
