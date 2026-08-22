from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

from stock_valuation.data.providers.esef import parse_esef_ixbrl


XHTML = b'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
      xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
  <body>
    <xbrli:context id="D2025">
      <xbrli:entity><xbrli:identifier scheme="lei">TEST</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period>
    </xbrli:context>
    <xbrli:context id="I2025">
      <xbrli:entity><xbrli:identifier scheme="lei">TEST</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period>
    </xbrli:context>
    <xbrli:unit id="EUR"><xbrli:measure>iso4217:EUR</xbrli:measure></xbrli:unit>
    <ix:nonFraction name="ifrs-full:Revenue" contextRef="D2025" unitRef="EUR" scale="6" format="ixt:num-dot-decimal">32,667.3</ix:nonFraction>
    <ix:nonFraction name="ifrs-full:ProfitLoss" contextRef="D2025" unitRef="EUR" scale="6" format="ixt:num-dot-decimal">9,609.4</ix:nonFraction>
    <ix:nonFraction name="ifrs-full:Assets" contextRef="I2025" unitRef="EUR" scale="6" format="ixt:num-dot-decimal">50,566.6</ix:nonFraction>
    <ix:nonFraction name="ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities" contextRef="D2025" unitRef="EUR" scale="6" sign="-" format="ixt:num-dot-decimal">1,573.6</ix:nonFraction>
  </body>
</html>'''


def test_esef_parser_maps_standard_ifrs_facts() -> None:
    facts = parse_esef_ixbrl(XHTML, filename="report.xhtml")
    by_metric = {fact.metric: fact for fact in facts}

    assert by_metric["revenue"].value == Decimal("32667300000.0")
    assert by_metric["net_income"].value == Decimal("9609400000.0")
    assert by_metric["total_assets"].value == Decimal("50566600000.0")
    assert by_metric["capital_expenditures"].value == Decimal("1573600000.0")
    assert by_metric["capital_expenditures"].provider_value == Decimal("-1573600000.0")
    assert by_metric["revenue"].currency == "EUR"
    assert by_metric["revenue"].provider == "esef_ixbrl"


def test_esef_parser_accepts_zip_packages() -> None:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("reports/main.xhtml", XHTML)
        archive.writestr("readme.txt", "test")

    facts = parse_esef_ixbrl(buffer.getvalue(), filename="package.zip")
    assert any(fact.metric == "revenue" for fact in facts)
