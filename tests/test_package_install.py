import importlib.util
from pathlib import Path
import re
import subprocess
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _toml_section(text: str, section_name: str) -> str:
    match = re.search(
        rf"(?ms)^\[{re.escape(section_name)}\]\s*$\n(.*?)(?=^\[|\Z)",
        text,
    )
    assert match is not None, f"missing [{section_name}] section"
    return match.group(1)


def _assert_toml_assignment(section: str, key: str, expected_value: str) -> None:
    pattern = rf"(?m)^{re.escape(key)}\s*=\s*{re.escape(expected_value)}\s*$"
    assert re.search(pattern, section) is not None, f"missing {key} = {expected_value}"


def test_package_metadata_only_includes_pricing_core():
    pyproject_text = (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project = _toml_section(pyproject_text, "project")
    setuptools = _toml_section(pyproject_text, "tool.setuptools")

    _assert_toml_assignment(project, "name", '"hanamans-pricing-core"')
    _assert_toml_assignment(project, "version", '"0.2.0"')
    _assert_toml_assignment(project, "requires-python", '">=3.10"')
    _assert_toml_assignment(project, "dependencies", "[]")
    _assert_toml_assignment(setuptools, "packages", '["pricing_core"]')


def test_installed_package_imports_outside_repository(tmp_path):
    if importlib.util.find_spec("setuptools") is None:
        pytest.skip("setuptools is not installed for a no-build-isolation smoke test")

    install_directory = tmp_path / "installed"
    working_directory = tmp_path / "outside-repository"
    working_directory.mkdir()

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            str(REPOSITORY_ROOT),
            "--target",
            str(install_directory),
            "--no-deps",
            "--no-build-isolation",
            "--disable-pip-version-check",
        ],
        check=True,
        cwd=working_directory,
        capture_output=True,
        text=True,
    )

    smoke_test = """
from importlib.metadata import distribution
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])

from pricing_core import (
    ProductPricePurchaseLimitResult,
    Settings,
    max_purchase_yen_for_product_price,
    max_purchase_yen_for_selling_total,
)

assert distribution("hanamans-pricing-core").metadata["Name"] == "hanamans-pricing-core"
assert Path(__import__("pricing_core").__file__).is_relative_to(Path(sys.argv[1]))
result = max_purchase_yen_for_selling_total(117.99, Settings(), 155)
assert result.max_purchase_yen == 8858
product_result = max_purchase_yen_for_product_price(117.99, Settings(), 155)
assert isinstance(product_result, ProductPricePurchaseLimitResult)
assert product_result.max_purchase_yen > result.max_purchase_yen
"""
    subprocess.run(
        [sys.executable, "-I", "-c", smoke_test, str(install_directory)],
        check=True,
        cwd=working_directory,
        capture_output=True,
        text=True,
    )
