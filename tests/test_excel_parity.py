import pytest

openpyxl = pytest.importorskip("openpyxl")
from openpyxl import Workbook

from calculator import Settings
from excel_writer import (
    _build_simulator_sheet,
    _candidate_fee_formula,
    _gui_audit_fee_formula,
    _shipping_table_rows,
)
from pricing_core import shipping_table_rows


def test_excel_uses_core_shipping_table():
    assert _shipping_table_rows() == shipping_table_rows()


def test_excel_formulas_preserve_fee_tax_shipping_refund_rules():
    wb = Workbook()
    ws = wb.active
    _build_simulator_sheet(ws)
    assert ws["B20"].value == '=IF($B$4="","",IF($B$4<2500,VLOOKUP($B$4,Settings!$A$34:$E$82,5,TRUE),0))'
    assert ws["B22"].value == '=IF($B$4="","",$B$21*$B$5*(1+$B$6))'
    assert "MIN($B$22," in ws["B24"].value
    assert "MAX($B$22-" in ws["B24"].value
    assert "Settings!$B$29" in ws["B24"].value
    assert "Settings!$B$30" in ws["B24"].value
    assert ws["B28"].value == '=IF($B$4="","",($B$23-$B$24-$B$26-$B$27)*$B$12)'
    assert ws["B29"].value == '=IF($B$4="","",$B$24+$B$26+$B$27+$B$28)'
    assert ws["B30"].value == '=IF($B$4="","",$B$7+$B$20*$B$5)'
    assert "0.0909" in ws["B33"].value and "*1.1*0.0909" in ws["B33"].value
    assert "($B$24-$B$25)/$B$22" in ws["B33"].value


def test_candidate_and_gui_fee_formulas_do_not_add_fixed_fee_twice():
    candidate = _candidate_fee_formula(88)
    gui = _gui_audit_fee_formula("B")
    assert candidate.count("Simulator!$B$9*Simulator!$B$5") == 2  # FVF and repeated inside Payoneer base
    assert gui.count("$B$9*$B$5") == 2  # FVF and repeated inside Payoneer base
    assert candidate.startswith("=(")
    assert gui.startswith('=IF(B45="","",')


def test_tiered_fvf_matches_across_candidate_and_gui_audit_formulas():
    for formula in (_candidate_fee_formula(88), _gui_audit_fee_formula("B")):
        assert "MIN(" in formula
        assert "MAX(" in formula
        assert "Settings!$B$29" in formula
        assert "Settings!$B$30" in formula
