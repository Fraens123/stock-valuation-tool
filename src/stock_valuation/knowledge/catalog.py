from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def load_metric_catalog() -> dict[str, dict]:
    path = Path(__file__).with_name("metrics.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["metrics"]


def get_metric_info(metric_id: str) -> dict | None:
    return load_metric_catalog().get(metric_id)


def list_metric_ids() -> list[str]:
    return list(load_metric_catalog())


def list_metrics_by_group(group: str) -> list[tuple[str, dict]]:
    return [
        (metric_id, info)
        for metric_id, info in load_metric_catalog().items()
        if info.get("group") == group
    ]
