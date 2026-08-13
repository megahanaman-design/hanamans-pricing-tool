import pytest

pytest.importorskip("openpyxl")

from app import _format_usd_ceil


def test_gui_usd_display_still_uses_ceil():
    assert _format_usd_ceil(99.01) == "$100"
    assert _format_usd_ceil(449.82) == "$450"
    assert _format_usd_ceil(None) == "該当なし"
