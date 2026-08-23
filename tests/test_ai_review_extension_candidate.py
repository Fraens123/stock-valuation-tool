import json
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.ai_review_service import (
    build_chatgpt_review_package,
    import_chatgpt_review_result,
)
from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.preferred_data import load_preferred_data_states
from stock_valuation.database.models import Base, FinancialFactSnapshot


def _add_fact(
    session: Session,
    analysis_id: int,
    *,
    metric: str,
    year: int,
    value: int,
    provider: str,
    provider_field: str,
) -> FinancialFactSnapshot:
    row = FinancialFactSnapshot(
        analysis_id=analysis_id,
        statement="cash_flow" if metric == "dividends_paid" else "income_statement",
        metric=metric,
        period_end=date(year, 12, 31),
        period_type="FY",
        value=Decimal(value),
        provider_value=Decimal(value),
        currency="EUR",
        unit="currency",
        provider=provider,
        provider_field=provider_field,
        source_type="primary_source",
        source_url="https://www.sec.gov/example.htm",
        is_cross_check_only=False,
        note=(
            "SEC Company-Extension-Kandidat für internes Feld dividends_paid; "
            "noch nicht semantisch freigegeben."
            if provider == "sec_filing_extension"
            else None
        ),
    )
    session.add(row)
    session.flush()
    return row


def test_old_extension_candidate_is_appended_to_recent_review_and_pass_unlocks_it() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(
            session,
            name="Example NV",
            ticker="EXM",
            currency="EUR",
        )
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        recent_2024 = _add_fact(
            session,
            analysis.id,
            metric="revenue",
            year=2024,
            value=1000,
            provider="sec_companyfacts",
            provider_field="us-gaap:Revenues",
        )
        recent_2025 = _add_fact(
            session,
            analysis.id,
            metric="revenue",
            year=2025,
            value=1100,
            provider="sec_companyfacts",
            provider_field="us-gaap:Revenues",
        )
        candidate = _add_fact(
            session,
            analysis.id,
            metric="dividends_paid",
            year=2019,
            value=300,
            provider="sec_filing_extension",
            provider_field="company-extension:DividendsPaidToShareholders",
        )
        session.commit()

        package = build_chatgpt_review_package(session, analysis, years=2)
        text = package.content.decode("utf-8")

        assert package.fact_count == 3
        assert str(candidate.id) in text
        assert "SEC-Company-Extension-Mappingkandidaten: 1" in text
        assert "noch nicht semantisch freigegeben" in text

        included = (recent_2024, recent_2025, candidate)
        payload = {
            "schema_version": "1.0",
            "package_id": package.package_id,
            "years_requested": package.years_requested,
            "company": {
                "name": "Example NV",
                "ticker": "EXM",
                "analysis_as_of_date": "2026-08-23",
                "revision": 1,
            },
            "summary": "All included facts verified.",
            "findings": [
                {
                    "fact_id": row.id,
                    "official_value": float(row.value),
                    "status": "PASS",
                    "official_label": row.provider_field,
                    "source_title": "Official filing",
                    "source_url": "https://www.sec.gov/example.htm",
                    "reason": "Exact semantic match.",
                }
                for row in included
            ],
        }
        import_chatgpt_review_result(session, analysis, json.dumps(payload))

        state = next(
            state
            for state in load_preferred_data_states(session, analysis.id)
            if state.fact.id == candidate.id
        )
        assert state.calculation_ready is True
        assert state.quality_status == "primary_reviewed_pass"
