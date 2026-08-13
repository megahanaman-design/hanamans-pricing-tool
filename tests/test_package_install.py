import importlib.util
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_package_metadata_only_includes_pricing_core():
    with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    assert pyproject["project"]["name"] == "hanamans-pricing-core"
    assert pyproject["project"]["version"] == "0.1.0"
    assert pyproject["project"]["dependencies"] == []
    assert pyproject["tool"]["setuptools"]["packages"] == ["pricing_core"]


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

from pricing_core import Settings, max_purchase_yen_for_selling_total

assert distribution("hanamans-pricing-core").metadata["Name"] == "hanamans-pricing-core"
assert Path(__import__("pricing_core").__file__).is_relative_to(Path(sys.argv[1]))
result = max_purchase_yen_for_selling_total(117.99, Settings(), 155)
assert result.max_purchase_yen == 8858
"""
    subprocess.run(
        [sys.executable, "-I", "-c", smoke_test, str(install_directory)],
        check=True,
        cwd=working_directory,
        capture_output=True,
        text=True,
    )
