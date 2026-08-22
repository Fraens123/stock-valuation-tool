from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def load_metric_catalog() -> dict:
    path = Path(__file__).with_name("metrics.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))["metrics"]


def get_metric_info(metric_id: str) -> dict | None:
    return load_metric_catalog().get(metric_id)
