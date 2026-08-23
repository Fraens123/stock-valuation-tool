from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from stock_valuation.quality.engine import evaluate_business_quality
from stock_valuation.quality.models import QualityCompanyResult, QualityInput


def evaluate_companies(inputs: Iterable[tuple[str, QualityInput]]) -> tuple[QualityCompanyResult, ...]:
    grouped: dict[str, list[QualityInput]] = defaultdict(list)
    for ticker, row in inputs:
        grouped[ticker].append(row)
    return tuple(
        evaluate_business_quality(ticker, grouped[ticker])
        for ticker in sorted(grouped)
    )
