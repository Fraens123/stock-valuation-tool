from __future__ import annotations

import importlib.metadata
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"


@dataclass(frozen=True)
class DependencyCheckResult:
    missing_before_install: tuple[str, ...]
    installed: tuple[str, ...]
    missing_after_install: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.missing_after_install


def _distribution_name(requirement: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", requirement)
    if match is None:
        raise ValueError(f"Ungueltige Abhaengigkeitsangabe: {requirement!r}")
    return match.group(1)


def runtime_dependency_specs(pyproject_path: Path = PYPROJECT) -> tuple[str, ...]:
    with pyproject_path.open("rb") as handle:
        data = tomllib.load(handle)
    dependencies = data.get("project", {}).get("dependencies", [])
    if not isinstance(dependencies, list):
        raise ValueError("`project.dependencies` in pyproject.toml ist ungueltig.")
    return tuple(str(item) for item in dependencies)


def missing_runtime_dependencies(requirements: tuple[str, ...]) -> tuple[str, ...]:
    missing: list[str] = []
    for requirement in requirements:
        distribution = _distribution_name(requirement)
        try:
            importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            missing.append(requirement)
    return tuple(missing)


def ensure_runtime_dependencies(
    *,
    pyproject_path: Path = PYPROJECT,
    auto_install: bool = True,
) -> DependencyCheckResult:
    requirements = runtime_dependency_specs(pyproject_path)
    missing_before = missing_runtime_dependencies(requirements)
    installed: tuple[str, ...] = ()

    if missing_before and auto_install:
        command = [sys.executable, "-m", "pip", "install", *missing_before]
        try:
            subprocess.check_call(command)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "Fehlende Python-Abhaengigkeiten konnten nicht automatisch installiert werden: "
                + " ".join(missing_before)
            ) from exc
        installed = missing_before

    missing_after = missing_runtime_dependencies(requirements)
    if missing_after:
        raise RuntimeError(
            "Fehlende Python-Abhaengigkeiten: "
            + ", ".join(missing_after)
            + '. Bitte ausfuehren: pip install -e ".[dev]"'
        )

    return DependencyCheckResult(
        missing_before_install=missing_before,
        installed=installed,
        missing_after_install=missing_after,
    )
