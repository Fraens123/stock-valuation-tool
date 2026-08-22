from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=8)
def load_provider_mapping(provider: str) -> dict:
    path = Path(__file__).with_name("mappings") / f"{provider}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Kein Feldmapping für Provider '{provider}' gefunden: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data.get("provider") != provider:
        raise ValueError(f"Provider-Mapping {path} enthält unerwarteten Provider.")
    return data


def iter_statement_mappings(provider: str):
    mapping = load_provider_mapping(provider)
    for statement in ("income_statement", "balance_sheet", "cash_flow"):
        for metric, spec in mapping.get(statement, {}).items():
            yield statement, metric, spec
