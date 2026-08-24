from __future__ import annotations

import importlib.metadata
from pathlib import Path

import pytest

from stock_valuation.runtime_dependencies import (
    ensure_runtime_dependencies,
    missing_runtime_dependencies,
    runtime_dependency_specs,
)


def test_runtime_dependency_specs_are_loaded_from_pyproject(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = [
  "requests>=2.32",
  "edgartools>=5.52",
]
""".strip(),
        encoding="utf-8",
    )

    assert runtime_dependency_specs(pyproject) == ("requests>=2.32", "edgartools>=5.52")


def test_missing_runtime_dependencies_use_distribution_names(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_version(name: str) -> str:
        if name == "edgartools":
            raise importlib.metadata.PackageNotFoundError(name)
        return "1.0"

    monkeypatch.setattr(importlib.metadata, "version", fake_version)

    assert missing_runtime_dependencies(("python-dotenv>=1.0", "edgartools>=5.52")) == (
        "edgartools>=5.52",
    )


def test_ensure_runtime_dependencies_installs_missing_packages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = [
  "requests>=2.32",
  "edgartools>=5.52",
]
""".strip(),
        encoding="utf-8",
    )
    installed: list[list[str]] = []
    available = {"requests"}

    def fake_version(name: str) -> str:
        if name not in available:
            raise importlib.metadata.PackageNotFoundError(name)
        return "1.0"

    def fake_check_call(command: list[str]) -> int:
        installed.append(command)
        available.add("edgartools")
        return 0

    monkeypatch.setattr(importlib.metadata, "version", fake_version)
    monkeypatch.setattr("subprocess.check_call", fake_check_call)

    result = ensure_runtime_dependencies(pyproject_path=pyproject)

    assert result.ok
    assert result.installed == ("edgartools>=5.52",)
    assert installed
    assert installed[0][-1] == "edgartools>=5.52"
