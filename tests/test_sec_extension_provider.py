from datetime import date
from decimal import Decimal

from stock_valuation.data.providers.sec_extension import (
    _candidate_facts_from_instance,
    parse_label_linkbase,
)


XBRL = """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl
    xmlns:xbrli="http://www.xbrl.org/2003/instance"
    xmlns:custom="http://example.com/company/2025"
    xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
  <xbrli:context id="D2025">
    <xbrli:entity><xbrli:identifier scheme="test">ENTITY</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period>
  </xbrli:context>
  <xbrli:context id="I2025">
    <xbrli:entity><xbrli:identifier scheme="test">ENTITY</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period>
  </xbrli:context>
  <xbrli:unit id="EUR"><xbrli:measure>iso4217:EUR</xbrli:measure></xbrli:unit>
  <custom:DividendsPaidToShareholders contextRef="D2025" unitRef="EUR">300</custom:DividendsPaidToShareholders>
  <custom:NetCashProvidedByOperatingActivities contextRef="D2025" unitRef="EUR">1250</custom:NetCashProvidedByOperatingActivities>
  <custom:CurrentPortionOfLongTermDebt contextRef="I2025" unitRef="EUR">247</custom:CurrentPortionOfLongTermDebt>
</xbrli:xbrl>
"""


def test_extension_candidates_are_mapped_only_as_review_candidates() -> None:
    facts = _candidate_facts_from_instance(
        XBRL,
        target_metrics={"dividends_paid", "operating_cash_flow", "short_term_debt"},
        report_date=date(2025, 12, 31),
        filing_date=date(2026, 2, 1),
        form="20-F",
        source_url="https://www.sec.gov/example_htm.xml",
        expected_currency="EUR",
        labels={
            "custom_DividendsPaidToShareholders": "Dividends paid to shareholders",
            "custom_NetCashProvidedByOperatingActivities": "Net cash provided by operating activities",
            "custom_CurrentPortionOfLongTermDebt": "Current portion of long-term debt",
        },
    )

    assert set(facts) == {"dividends_paid", "operating_cash_flow", "short_term_debt"}
    assert facts["dividends_paid"].value == Decimal("300")
    assert facts["operating_cash_flow"].value == Decimal("1250")
    assert facts["short_term_debt"].value == Decimal("247")
    assert all(fact.provider == "sec_filing_extension" for fact in facts.values())
    assert all(fact.source_url == "https://www.sec.gov/example_htm.xml" for fact in facts.values())
    assert "noch nicht semantisch freigegeben" in facts["dividends_paid"].note


def test_declared_dividend_is_not_a_paid_dividend_candidate() -> None:
    xml = XBRL.replace(
        '<custom:DividendsPaidToShareholders contextRef="D2025" unitRef="EUR">300</custom:DividendsPaidToShareholders>',
        '<custom:DividendsDeclared contextRef="D2025" unitRef="EUR">300</custom:DividendsDeclared>',
    )
    facts = _candidate_facts_from_instance(
        xml,
        target_metrics={"dividends_paid"},
        report_date=date(2025, 12, 31),
        filing_date=date(2026, 2, 1),
        form="20-F",
        source_url="https://www.sec.gov/example_htm.xml",
        expected_currency="EUR",
        labels={"custom_DividendsDeclared": "Dividends declared"},
    )

    assert facts == {}


def test_label_linkbase_extracts_human_label() -> None:
    label_xml = """<?xml version="1.0"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:labelLink xlink:type="extended">
    <link:loc xlink:type="locator" xlink:href="company.xsd#custom_DividendsPaidToShareholders" xlink:label="loc1"/>
    <link:label xlink:type="resource" xlink:label="lab1">Dividends paid to shareholders</link:label>
    <link:labelArc xlink:type="arc" xlink:from="loc1" xlink:to="lab1"/>
  </link:labelLink>
</link:linkbase>
"""
    labels = parse_label_linkbase(label_xml)

    assert labels["custom_DividendsPaidToShareholders"] == "Dividends paid to shareholders"
