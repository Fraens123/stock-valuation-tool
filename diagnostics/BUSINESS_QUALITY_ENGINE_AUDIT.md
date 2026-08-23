# BUSINESS_QUALITY_ENGINE_AUDIT

## 1. Executive Summary

Decision: GO – BUSINESS QUALITY ENGINE V1 FROZEN

Business Quality Engine V1 wurde als eigenstaendige Schicht unter `src/stock_valuation/quality/` implementiert. Sie nutzt ausschliesslich Calculation Engine V1 und Historical Analysis Engine V1 Outputs; keine Providerdaten, keine SEC-Rohfacts, keine Marktpreise.

## 2. Bestehende Quality-/Schmidlin-Logik

- Keine bestehende produktive Business-Quality-Engine gefunden.
- Vorhandene `score`-Felder in SEC-Extension/Text-Parsing sind technische Matching-Scores, keine Unternehmensqualitaetsbewertung.
- `docs/PHASE_1_METRIC_INVENTORY.md`, `docs/OPEN_ITEMS.md` und `docs/QUALITATIVE_ANALYSIS_SPEC.md` enthalten Schmidlin-/Excel-Kontext, aber keine verifizierte automatische Quality-Punktelogik fuer V1.
- Deshalb wurden bestehende Formeln/Schwellen nicht ungeprueft uebernommen.

## 3. Verwendete Kennzahlen

gross_margin_quality, operating_margin_quality, net_margin_quality, ebitda_margin_quality, free_cash_flow_margin_quality, fcf_to_ocf_quality, ocf_to_net_income_quality, fcf_to_net_income_quality, return_on_assets_quality, return_on_equity_quality, roic_quality, equity_ratio_quality, debt_to_assets_quality, debt_to_equity_quality, net_debt_to_ebitda_quality, current_ratio_quality, quick_ratio_quality, cash_ratio_quality, capex_intensity_quality, revenue_growth_quality, earnings_growth_quality, fcf_growth_quality, margin_volatility_quality, growth_volatility_quality, negative_years_quality, missing_years_quality, inventory_applicability_quality

## 4. Formeln und Definitionen

| ID | Name | Kategorie | Formel | Inputs | Einheit | Bedeutung | Grenzen | Geeignet | Nicht geeignet | Quelle |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gross_margin_quality | Gross Margin Quality | margin_quality | latest gross_margin plus 3-year trend and volatility context | gross_margin | decimal_ratio | Gross margin shows how much revenue remains after direct production or service costs. | Cross-industry comparisons can be distorted by revenue recognition and outsourcing depth. | Software, semiconductor, industrial, consumer, asset-light, asset-heavy. | Financial companies and businesses with non-standard gross-profit presentation. | GENERAL_FINANCIAL_ANALYSIS |
| operating_margin_quality | Operating Margin Quality | profitability | latest operating_margin | operating_margin | decimal_ratio | Operating margin measures operating profit per unit of revenue. | Capitalized costs and cyclicality can distort one-year margins. | Most non-financial operating businesses. | Early-stage loss companies without mature economics. | GENERAL_FINANCIAL_ANALYSIS |
| net_margin_quality | Net Margin Quality | profitability | latest net_margin | net_margin | decimal_ratio | Net margin captures profit after all reported expenses. | Tax, financing and one-off items can dominate. | Most non-financial companies. | Banks/insurers require separate method. | GENERAL_FINANCIAL_ANALYSIS |
| ebitda_margin_quality | EBITDA Margin Quality | margin_quality | latest ebitda_margin | ebitda_margin | decimal_ratio | EBITDA margin strips D&A from operating income using internal EBITDA only. | Can overstate quality for asset-heavy businesses with high reinvestment needs. | Most non-financial operating businesses. | Businesses where D&A is economically central and capex data is incomplete. | GENERAL_FINANCIAL_ANALYSIS |
| free_cash_flow_margin_quality | Free Cash Flow Margin Quality | cashflow_quality | latest free_cash_flow_margin | free_cash_flow_margin | decimal_ratio | FCF margin measures post-capex cash generation relative to revenue. | Growth investment cycles can depress FCF temporarily. | Mature asset-light and asset-heavy businesses with meaningful capex. | Companies with structurally irregular project cash flows need review. | GENERAL_FINANCIAL_ANALYSIS |
| fcf_to_ocf_quality | FCF / Operating Cash Flow | cashflow_quality | 1 - capex_ratio | capex_ratio | decimal_ratio | Shows the share of operating cash flow left after PPE capex. | Can penalize growth investment if interpreted without context. | Most companies with recurring capex. | Companies with lumpy expansion projects in a short history. | PROJECT_EXTENSION |
| ocf_to_net_income_quality | Operating Cash Flow / Net Income | cashflow_quality | not implemented in V1 because raw net_income and OCF are not both exposed by Calculation/Historical outputs as same-year measures | operating_cash_flow, net_income | decimal_ratio | Would test earnings-to-cash conversion. | Not available from current frozen output surface without reaching around the engines. | Most profitable non-financial companies. | Loss years require separate interpretation. | GENERAL_FINANCIAL_ANALYSIS |
| fcf_to_net_income_quality | Free Cash Flow / Net Income | cashflow_quality | not implemented in V1 because raw net_income is not exposed by Calculation/Historical outputs as same-year measure | free_cash_flow, net_income | decimal_ratio | Would compare post-capex cash with accounting profit. | Can be distorted by investment cycles. | Mature non-financial companies. | Loss years and heavy investment phases. | GENERAL_FINANCIAL_ANALYSIS |
| return_on_assets_quality | Return on Assets Quality | capital_efficiency | latest return_on_assets | return_on_assets | decimal_ratio | ROA measures profit relative to asset base. | Asset-light and asset-heavy businesses are not directly comparable. | Most non-financial companies. | Financial companies need sector-specific asset logic. | GENERAL_FINANCIAL_ANALYSIS |
| return_on_equity_quality | Return on Equity Quality | capital_efficiency | latest return_on_equity | return_on_equity | decimal_ratio | ROE measures profit relative to book equity. | Low equity or buybacks can inflate ROE. | Companies with positive meaningful equity. | Negative or tiny equity base. | GENERAL_FINANCIAL_ANALYSIS |
| roic_quality | ROIC Quality | capital_efficiency | not implemented in V1; invested capital requires a reviewed operating capital definition | nopat, invested_capital | decimal_ratio | ROIC would measure returns on operating invested capital. | Current data lacks tax-normalized NOPAT and reviewed invested-capital adjustments. | Industrial and operating businesses after definition review. | Not reliable without reviewed invested capital. | PROJECT_EXTENSION |
| equity_ratio_quality | Equity Ratio Quality | balance_sheet | latest equity_ratio | equity_ratio | decimal_ratio | Shows book equity buffer relative to total assets. | Asset-light companies may operate with lower book equity. | Most non-financial companies. | Financials need regulatory capital metrics. | GENERAL_FINANCIAL_ANALYSIS |
| debt_to_assets_quality | Debt to Assets Quality | balance_sheet | latest debt_to_assets | debt_to_assets | decimal_ratio | Interest-bearing debt relative to assets. | Cash-rich companies need net-debt context. | Most non-financial companies. | Financial companies. | GENERAL_FINANCIAL_ANALYSIS |
| debt_to_equity_quality | Debt to Equity Quality | balance_sheet | latest debt_to_equity | debt_to_equity | decimal_ratio | Interest-bearing debt relative to equity. | Distorted by low or negative equity. | Companies with stable positive equity. | Negative-equity cases without manual review. | GENERAL_FINANCIAL_ANALYSIS |
| net_debt_to_ebitda_quality | Net Debt / EBITDA Quality | balance_sheet | latest net_debt_to_ebitda | net_debt_to_ebitda | decimal_ratio | Net leverage relative to internal EBITDA. | Negative EBITDA needs special handling upstream. | Most non-financial operating companies. | Loss-making companies with negative EBITDA. | GENERAL_FINANCIAL_ANALYSIS |
| current_ratio_quality | Current Ratio Quality | balance_sheet | latest current_ratio | current_ratio | decimal_ratio | Broad short-term liquidity. | High values are not always better if capital is idle. | Most non-financial companies. | Financials and businesses with structurally negative working capital need context. | GENERAL_FINANCIAL_ANALYSIS |
| quick_ratio_quality | Quick Ratio Quality | balance_sheet | latest quick_ratio | quick_ratio | decimal_ratio | Liquidity excluding inventory. | Receivable collectability is not evaluated. | Software, semiconductor, industrial, consumer. | Financials. | GENERAL_FINANCIAL_ANALYSIS |
| cash_ratio_quality | Cash Ratio Quality | balance_sheet | latest cash_ratio | cash_ratio | decimal_ratio | Immediate cash coverage of current liabilities. | Excess cash can reduce returns; not a valuation signal. | Most non-financial companies. | Financials. | GENERAL_FINANCIAL_ANALYSIS |
| capex_intensity_quality | Investment Intensity Quality | cashflow_quality | latest capex_ratio plus trend context | capex_ratio | decimal_ratio | Shows OCF share reinvested into PPE. | Asset-heavy growth phases can be intentionally high. | Semiconductor, industrial, consumer, asset-heavy and asset-light with context. | Businesses with irregular project capex need longer history. | PROJECT_EXTENSION |
| revenue_growth_quality | Revenue Growth Quality | growth | latest revenue YoY and 3Y CAGR where available | revenue | decimal_ratio | Measures top-line growth over time. | Growth alone is not quality without margins and cash flow. | Most operating companies. | Turnarounds and cyclical troughs require review. | GENERAL_FINANCIAL_ANALYSIS |
| earnings_growth_quality | Earnings Growth Quality | growth | latest net_income YoY and 3Y CAGR where available | net_income | decimal_ratio | Measures reported earnings growth. | Negative base years are not forced into bad scores; upstream status is preserved. | Profitable companies. | Loss-making or turnaround companies. | GENERAL_FINANCIAL_ANALYSIS |
| fcf_growth_quality | FCF Growth Quality | growth | latest free_cash_flow YoY and 3Y CAGR where available | free_cash_flow | decimal_ratio | Measures cash generation growth. | Capex cycles can distort short windows. | Cash-generative companies. | Businesses with lumpy project cash flows. | GENERAL_FINANCIAL_ANALYSIS |
| margin_volatility_quality | Margin Volatility Quality | stability | average of per-series population volatility for gross_margin, operating_margin, net_margin, ebitda_margin and free_cash_flow_margin | gross_margin, operating_margin, net_margin, ebitda_margin, free_cash_flow_margin | decimal_ratio | Measures time-series stability of each margin and aggregates the available series volatilities. | Three-year windows are short and can miss cycles; cross-margin level dispersion is deliberately not measured. | Most non-financial companies. | Highly cyclical companies need longer history. | PROJECT_EXTENSION |
| growth_volatility_quality | Growth Volatility Quality | stability | average of per-series population volatility for revenue, net_income and free_cash_flow YoY growth | revenue, net_income, free_cash_flow | decimal_ratio | Measures time-series variability of each growth metric and aggregates the available series volatilities. | Short history and negative-base suppression can reduce sample size. | Most operating companies. | Turnarounds and cyclicals need manual context. | PROJECT_EXTENSION |
| negative_years_quality | Negative Years Quality | stability | negative_years from Historical Analysis stability profile | revenue, net_income, free_cash_flow | count | Counts negative reported years in relevant series. | Negative FCF during investment phases is not automatically fatal. | Most mature companies. | Early-stage loss companies. | PROJECT_EXTENSION |
| missing_years_quality | Missing Years Data Confidence | data_confidence | missing_years from Historical Analysis stability profile | revenue, net_income, free_cash_flow | count | Counts missing/unavailable years in the historical window. | Only measures data completeness, not business quality directly. | All companies. | None; missing data is not treated as bad business economics. | PROJECT_EXTENSION |
| inventory_applicability_quality | Inventory Applicability | working_capital | inventory_intensity/inventory_days availability status | inventory_intensity, inventory_days | status | Separates business-model irrelevance from poor quality. | Does not judge supply-chain quality without inventory data. | Software and other asset-light companies; also inventory-heavy companies if reported. | None; status-only rule. | PROJECT_EXTENSION |

## 5. Availability-Regeln

- Status: AVAILABLE, UNAVAILABLE, NOT_APPLICABLE, INSUFFICIENT_HISTORY.
- Upstream-Status wie NOT_SEPARATELY_REPORTED, NEGATIVE_BASE und MISSING_PRIOR_YEAR werden respektiert.
- Fehlend wird nie als 0 behandelt.
- Nicht separat ausgewiesen wird nie als 0 behandelt.
- Nicht anwendbar ist kein negativer Score.

## 6. Geschaeftsmodellabhaengigkeit

- Software/asset-light: Inventory-bezogene Faktoren koennen NOT_APPLICABLE sein.
- Halbleiter/Industrie/asset-heavy: Capex-Intensitaet wird gezeigt, aber hohe Investitionen werden mit Grenzen dokumentiert.
- Consumer: Working-Capital- und Margentrends bleiben anwendbar, sofern upstream verfuegbar.
- Keine Branchen-Hardcodes in der Engine.

## 7. Schmidlin vs. Project Extensions

| Regelquelle | Umsetzung | Abweichung |
| --- | --- | --- |
| SCHMIDLIN | Keine Regel automatisch als Schmidlin-Regel markiert. | Schmidlin-Punktelogik ist im Repo nicht ausreichend verifiziert. |
| GENERAL_FINANCIAL_ANALYSIS | Margen, Renditen, Bilanz, Liquiditaet, Wachstum. | Schwellen sind breite dokumentierte V1-Anker, keine Schmidlin-Behauptung. |
| PROJECT_EXTENSION | Volatilitaet, Missing/Negative-Year-Qualitaet, Inventory-Appplicability, FCF/OCF aus Capex-Ratio. | Projektinterne, testbare Erweiterungen. |

## 8. Scoring-Modell

- Messwert, Interpretation und Score sind getrennte Felder.
- Scores liegen auf 0 bis 10.
- Nicht verfuegbare und nicht anwendbare Faktoren gehen nicht als 0 in den Score ein.
- Overall Quality Score ist ein gewichteter Durchschnitt verfuegbarer Komponenten.

## 9. Gewichtungen

| Komponente | Gewicht | Begruendung |
| --- | ---: | --- |
| profitability | 18% | Profitabilitaet ist zentral, aber nicht allein ausreichend. |
| margin_quality | 14% | Margen zeigen oekonomische Qualitaet und Preissetzung. |
| cashflow_quality | 16% | Cash Conversion und Capex-Intensitaet schuetzen vor reiner Accounting-Qualitaet. |
| growth | 14% | Wachstum ist wichtig, aber nur mit Profitabilitaet hochwertig. |
| balance_sheet | 14% | Finanzkraft reduziert Fragilitaet. |
| capital_efficiency | 14% | Rendite auf Kapital zeigt Effizienz. |
| stability | 10% | Stabilitaet erhoeht Vertrauen in die Historie. |

## 10-14. Regressionen

| Unternehmen | Jahre | Profitabilitaet | Margenentwicklung | Cashflow-Qualitaet | Wachstum | Bilanzqualitaet | Kapitalrenditen | Score | Assessment |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| AAPL | 2023, 2024, 2025 | 8 | 9 | 8.333333333333333333333333333 | 5.333333333333333333333333333 | 5.885092156836152062170262976 | 9 | 7.707323658043125340595157266 | SOLID |
| ADBE | 2023, 2024, 2025 | 8 | 9 | 9 | 8.333333333333333333333333333 | 6.857142857142857142857142857 | 8 | 8.255825793366261170620653158 | STRONG |
| ASML | 2023, 2024, 2025 | 8 | 9 | 9 | 7.666666666666666666666666667 | 7.142857142857142857142857143 | 8 | 8.033333333333333333333333333 | STRONG |
| MSFT | 2024, 2025, 2026 | 9 | 9 | 6.646252615531321082473131013 | 7.333333333333333333333333333 | 6.857142857142857142857142857 | 8 | 7.971099601711631218802991919 | SOLID |
| TSM | 2023, 2024, 2025 | 9 | 9 | 6.936027098976846657656948547 | 9 | 8.571428571428571428571428571 | 8 | 8.266973142126208103773367806 | STRONG |

## 15. Gefundene Probleme

- Keine blockierenden Quality-Engine-Probleme.

## 16. Verbleibende Einschraenkungen

- OCF/Net Income und FCF/Net Income sind in V1 nicht scored, weil die frozen Calculation/Historical-Artefakte Net Income nicht als same-year Quality-Input zusammen mit Cashflow exponieren.
- ROIC ist nicht implementiert, weil Invested Capital und NOPAT fuer V1 nicht fachlich sauber freigegeben sind.
- Missing Years ist Data Confidence, nicht Business Quality, und beeinflusst den Overall Quality Score nicht.
- 5Y/10Y-Aussagen bleiben bei nur drei freigegebenen Jahren INSUFFICIENT_HISTORY.
- Absolute Score-Bands sind breite V1-Anker und keine branchenspezifische Bewertung.

## 17. Zielarchitektur

- `quality/models.py`: Datenmodelle und Status.
- `quality/rules.py`: Definitionen, Formeln, Quellenkategorien.
- `quality/scoring.py`: konfigurierbare Scores und Gewichtungen.
- `quality/engine.py`: providerunabhaengige Auswertung.
- `quality/service.py`: Mehr-Unternehmen-Service.

## 18. Testergebnis

Unit- und Regressionstests liegen in `tests/test_business_quality_engine.py`. Die komplette Testsuite muss nach diesem Audit erfolgreich laufen.

## 19. GO/NO-GO-Entscheidung

GO – BUSINESS QUALITY ENGINE V1 FROZEN

## 20. Ergebnisdarstellung pro Unternehmen

### AAPL

- Geschaeftsjahre: 2023, 2024, 2025
- Quality Score: 7.707323658043125340595157266
- Quality Assessment: SOLID
- Positive Faktoren: Gross Margin Quality: STRONG; Operating Margin Quality: STRONG; EBITDA Margin Quality: STRONG; FCF / Operating Cash Flow: STRONG; Return on Assets Quality: STRONG; Return on Equity Quality: STRONG; Debt to Assets Quality: STRONG; Debt to Equity Quality: STRONG
- Negative Faktoren: Quick Ratio Quality: WEAK; Cash Ratio Quality: WEAK
- Nicht verfuegbare Faktoren: Operating Cash Flow / Net Income: UPSTREAM_MEASURE_NOT_EXPOSED; Free Cash Flow / Net Income: UPSTREAM_MEASURE_NOT_EXPOSED; ROIC Quality: UPSTREAM_MEASURE_NOT_EXPOSED
- Nicht anwendbare Faktoren: keine
- Business-Model-Logik: Keine firmenspezifischen Hardcodes; die Engine bewertet nur Datenverfuegbarkeit, Werte, Trends und Volatilitaet. Asset-light/Software: Inventory-Status NOT_SEPARATELY_REPORTED fuehrt zu NOT_APPLICABLE, nicht zu einer negativen Bewertung. Asset-heavy/Halbleiter/Industrie: Capex-Intensitaet wird ausgewiesen, aber hohe Investitionen werden als Kontextgrenze dokumentiert. US-GAAP/IFRS/Foreign Private Issuer: Die Engine sieht nur Calculation/Historical-Ergebnisse und ist providerunabhaengig.

### ADBE

- Geschaeftsjahre: 2023, 2024, 2025
- Quality Score: 8.255825793366261170620653158
- Quality Assessment: STRONG
- Positive Faktoren: Gross Margin Quality: STRONG; Operating Margin Quality: STRONG; EBITDA Margin Quality: STRONG; Free Cash Flow Margin Quality: STRONG; FCF / Operating Cash Flow: STRONG; Return on Equity Quality: STRONG; Equity Ratio Quality: STRONG; Debt to Assets Quality: STRONG
- Negative Faktoren: keine
- Nicht verfuegbare Faktoren: Operating Cash Flow / Net Income: UPSTREAM_MEASURE_NOT_EXPOSED; Free Cash Flow / Net Income: UPSTREAM_MEASURE_NOT_EXPOSED; ROIC Quality: UPSTREAM_MEASURE_NOT_EXPOSED
- Nicht anwendbare Faktoren: Inventory Applicability: INVENTORY_NOT_SEPARATELY_REPORTED
- Business-Model-Logik: Keine firmenspezifischen Hardcodes; die Engine bewertet nur Datenverfuegbarkeit, Werte, Trends und Volatilitaet. Asset-light/Software: Inventory-Status NOT_SEPARATELY_REPORTED fuehrt zu NOT_APPLICABLE, nicht zu einer negativen Bewertung. Asset-heavy/Halbleiter/Industrie: Capex-Intensitaet wird ausgewiesen, aber hohe Investitionen werden als Kontextgrenze dokumentiert. US-GAAP/IFRS/Foreign Private Issuer: Die Engine sieht nur Calculation/Historical-Ergebnisse und ist providerunabhaengig. Nicht anwendbare Faktoren: Inventory Applicability: INVENTORY_NOT_SEPARATELY_REPORTED

### ASML

- Geschaeftsjahre: 2023, 2024, 2025
- Quality Score: 8.033333333333333333333333333
- Quality Assessment: STRONG
- Positive Faktoren: Gross Margin Quality: STRONG; Operating Margin Quality: STRONG; EBITDA Margin Quality: STRONG; Free Cash Flow Margin Quality: STRONG; FCF / Operating Cash Flow: STRONG; Return on Equity Quality: STRONG; Equity Ratio Quality: STRONG; Debt to Assets Quality: STRONG
- Negative Faktoren: Growth Volatility Quality: WEAK
- Nicht verfuegbare Faktoren: Operating Cash Flow / Net Income: UPSTREAM_MEASURE_NOT_EXPOSED; Free Cash Flow / Net Income: UPSTREAM_MEASURE_NOT_EXPOSED; ROIC Quality: UPSTREAM_MEASURE_NOT_EXPOSED
- Nicht anwendbare Faktoren: keine
- Business-Model-Logik: Keine firmenspezifischen Hardcodes; die Engine bewertet nur Datenverfuegbarkeit, Werte, Trends und Volatilitaet. Asset-light/Software: Inventory-Status NOT_SEPARATELY_REPORTED fuehrt zu NOT_APPLICABLE, nicht zu einer negativen Bewertung. Asset-heavy/Halbleiter/Industrie: Capex-Intensitaet wird ausgewiesen, aber hohe Investitionen werden als Kontextgrenze dokumentiert. US-GAAP/IFRS/Foreign Private Issuer: Die Engine sieht nur Calculation/Historical-Ergebnisse und ist providerunabhaengig.

### MSFT

- Geschaeftsjahre: 2024, 2025, 2026
- Quality Score: 7.971099601711631218802991919
- Quality Assessment: SOLID
- Positive Faktoren: Gross Margin Quality: STRONG; Operating Margin Quality: STRONG; Net Margin Quality: STRONG; EBITDA Margin Quality: STRONG; FCF / Operating Cash Flow: STRONG; Return on Equity Quality: STRONG; Equity Ratio Quality: STRONG; Debt to Assets Quality: STRONG
- Negative Faktoren: Cash Ratio Quality: WEAK; Investment Intensity Quality: WEAK
- Nicht verfuegbare Faktoren: Operating Cash Flow / Net Income: UPSTREAM_MEASURE_NOT_EXPOSED; Free Cash Flow / Net Income: UPSTREAM_MEASURE_NOT_EXPOSED; ROIC Quality: UPSTREAM_MEASURE_NOT_EXPOSED
- Nicht anwendbare Faktoren: keine
- Business-Model-Logik: Keine firmenspezifischen Hardcodes; die Engine bewertet nur Datenverfuegbarkeit, Werte, Trends und Volatilitaet. Asset-light/Software: Inventory-Status NOT_SEPARATELY_REPORTED fuehrt zu NOT_APPLICABLE, nicht zu einer negativen Bewertung. Asset-heavy/Halbleiter/Industrie: Capex-Intensitaet wird ausgewiesen, aber hohe Investitionen werden als Kontextgrenze dokumentiert. US-GAAP/IFRS/Foreign Private Issuer: Die Engine sieht nur Calculation/Historical-Ergebnisse und ist providerunabhaengig.

### TSM

- Geschaeftsjahre: 2023, 2024, 2025
- Quality Score: 8.266973142126208103773367806
- Quality Assessment: STRONG
- Positive Faktoren: Gross Margin Quality: STRONG; Operating Margin Quality: STRONG; Net Margin Quality: STRONG; EBITDA Margin Quality: STRONG; FCF / Operating Cash Flow: STRONG; Return on Equity Quality: STRONG; Equity Ratio Quality: STRONG; Debt to Assets Quality: STRONG
- Negative Faktoren: Growth Volatility Quality: WEAK
- Nicht verfuegbare Faktoren: Operating Cash Flow / Net Income: UPSTREAM_MEASURE_NOT_EXPOSED; Free Cash Flow / Net Income: UPSTREAM_MEASURE_NOT_EXPOSED; ROIC Quality: UPSTREAM_MEASURE_NOT_EXPOSED
- Nicht anwendbare Faktoren: keine
- Business-Model-Logik: Keine firmenspezifischen Hardcodes; die Engine bewertet nur Datenverfuegbarkeit, Werte, Trends und Volatilitaet. Asset-light/Software: Inventory-Status NOT_SEPARATELY_REPORTED fuehrt zu NOT_APPLICABLE, nicht zu einer negativen Bewertung. Asset-heavy/Halbleiter/Industrie: Capex-Intensitaet wird ausgewiesen, aber hohe Investitionen werden als Kontextgrenze dokumentiert. US-GAAP/IFRS/Foreign Private Issuer: Die Engine sieht nur Calculation/Historical-Ergebnisse und ist providerunabhaengig.

## 21. Abschlussentscheidung

GO – BUSINESS QUALITY ENGINE V1 FROZEN
