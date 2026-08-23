from __future__ import annotations

from stock_valuation.market.models import ListingData


def choose_listing(candidates: list[ListingData]) -> ListingData | None:
    if not candidates:
        return None
    primary = [item for item in candidates if item.primary_listing and item.security_type.lower() not in {"adr", "ads"}]
    if primary:
        return sorted(primary, key=lambda item: item.ticker)[0]
    ordinary = [item for item in candidates if item.security_type.lower() not in {"adr", "ads"}]
    if ordinary:
        return sorted(ordinary, key=lambda item: item.ticker)[0]
    eligible_adr = [
        item
        for item in candidates
        if item.security_type.upper() in {"ADR", "ADS"}
        and item.adr_ratio is not None
        and item.underlying_share_ratio is not None
    ]
    return sorted(eligible_adr, key=lambda item: item.ticker)[0] if eligible_adr else None
