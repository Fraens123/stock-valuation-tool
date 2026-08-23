from datetime import date
from decimal import Decimal

from stock_valuation.data.providers.sec_filing import (
    SECFilingFallbackProvider,
    SECFilingRef,
    parse_xbrl_instance,
)
from stock_valuation.data.types import NormalizedFinancialFact


XBRL = """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl
    xmlns:xbrli="http://www.xbrl.org/2003/instance"
    xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
    xmlns:us-gaap="http://fasb.org/us-gaap/2025"
    xmlns:custom="http://example.com/custom/2025"
    xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
  <xbrli:context id="D2025">
    <xbrli:entity><xbrli:identifier scheme="test">ENTITY</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period>
  </xbrli:context>
  <xbrli:context id="I2025">
    <xbrli:entity><xbrli:identifier scheme="test">ENTITY</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period>
  </xbrli:context>
  <xbrli:context id="D2025SEG">
    <xbrli:entity>
      <xbrli:identifier scheme="test">ENTITY</xbrli:identifier>
      <xbrli:segment><xbrldi:explicitMember dimension="custom:SegmentAxis">custom:A</xbrldi:explicitMember></xbrli:segment>
    </xbrli:entity>
    <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period>
  </xbrli:context>
  <xbrli:unit id="EUR"><xbrli:measure>iso4217:EUR</xbrli:measure></xbrli:unit>
  <us-gaap:NetCashProvidedByUsedInOperatingActivities contextRef="D2025" unitRef="EUR">1250</us-gaap:NetCashProvidedByUsedInOperatingActivities>
  <us-gaap:Assets contextRef="I2025" unitRef="EUR">5000</us-gaap:Assets>
  <us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax contextRef="D2025SEG" unitRef="EUR">9999</us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax>
  <custom:DividendsPaidToShareholders contextRef="D2025" unitRef="EUR">300</custom:DividendsPaidToShareholders>
</xbrli:xbrl>
"""


def test_original_filing_parser_imports_only_standard_entity_wide_annual_facts() -> None:
    facts = parse_xbrl_instance(
        XBRL,
        report_date=date(2025, 12, 31),
        filing_date=date(2026, 2, 1),
        form="20-F",
        source_url="https://www.sec.gov/example_htm.xml",
        expected_currency="EUR",
    )
    by_metric = {fact.metric: fact for fact in facts}

    assert set(by_metric) == {"operating_cash_flow", "total_assets"}
    assert by_metric["operating_cash_flow"].value == Decimal("1250")
    assert by_metric["operating_cash_flow"].provider == "sec_filing_xbrl"
    assert by_metric["operating_cash_flow"].provider_field == (
        "us-gaap:NetCashProvidedByUsedInOperatingActivities"
    )
    assert by_metric["total_assets"].value == Decimal("5000")
    assert all(fact.source_url == "https://www.sec.gov/example_htm.xml" for fact in facts)


def test_original_filing_parser_keeps_short_term_debt_as_raw_standard_fact() -> None:
    xml = XBRL.replace(
        "</xbrli:xbrl>",
        '<us-gaap:LongTermDebtCurrent contextRef="I2025" unitRef="EUR">247</us-gaap:LongTermDebtCurrent></xbrli:xbrl>',
    )
    facts = parse_xbrl_instance(
        xml,
        report_date=date(2025, 12, 31),
        filing_date=date(2026, 2, 1),
        form="20-F",
        source_url="https://www.sec.gov/example_htm.xml",
        expected_currency="EUR",
    )
    debt = next(fact for fact in facts if fact.metric == "short_term_debt")

    assert debt.value == Decimal("247")
    assert debt.provider_field == "us-gaap:LongTermDebtCurrent"


def _base_fact(metric: str, value: int) -> NormalizedFinancialFact:
    return NormalizedFinancialFact(
        statement="income_statement",
        metric=metric,
        period_end=date(2024, 12, 31),
        period_type="FY",
        value=Decimal(value),
        provider_value=Decimal(value),
        currency="EUR",
        unit="currency",
        provider="sec_companyfacts",
        provider_field=f"us-gaap:{metric}",
    )


class LatestFilingProvider(SECFilingFallbackProvider):
    def __init__(self) -> None:
        pass

    def list_annual_filings(self, cik: str, *, target_years=None):
        return [
            SECFilingRef(
                accession_number="0000000000-26-000001",
                filing_date=date(2026, 4, 1),
                report_date=date(2025, 12, 31),
                form="20-F",
                primary_document="example.htm",
            )
        ]

    def filings_for_year(self, cik: str, year: int):
        return [ref for ref in self.list_annual_filings(cik) if ref.report_date.year == year]

    def _instance_document(self, cik: str, filing: SECFilingRef):
        return "https://www.sec.gov/example_htm.xml", XBRL


def test_original_filing_fallback_imports_latest_year_missing_from_companyfacts() -> None:
    provider = LatestFilingProvider()

    result = provider.gap_facts(
        "0000123456",
        [_base_fact("operating_cash_flow", 100), _base_fact("total_assets", 500)],
        years=3,
    )
    by_metric = {fact.metric: fact for fact in result.facts}

    assert set(by_metric) == {"operating_cash_flow", "total_assets"}
    assert by_metric["operating_cash_flow"].period_end == date(2025, 12, 31)
    assert by_metric["operating_cash_flow"].value == Decimal("1250")
    assert by_metric["operating_cash_flow"].note.endswith("accn=0000000000-26-000001")
    assert [gap for gap in result.unresolved if gap.year == 2025] == []
