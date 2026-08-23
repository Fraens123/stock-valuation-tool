# Excel Valuation Formula Map

Quelle: `Bewertung Kone Aufzüge.xlsm`, Blatt `Krones`, Bereich ca. Zeile 397-701.

Status: ausgewertet für Phase 9B. Die bestehende Frozen-Valuation-Engine bleibt erhalten. Die neue Methodik ist versioniert als `excel-book-valuation-v1.0`.

## Bewertungskennzahlen

| Excel-Zelle | Excel-Bezeichnung | Excel-Formel | Fachliche Bedeutung | App-Backend-Input | Neue App-Formel | Status | Abweichung / Hinweis |
|---|---|---|---|---|---|---|---|
| I398 | Aktueller Kurs | Eingabewert | Marktpreis je Aktie | MarketDataSnapshotRecord.price | Kurs aus Snapshot oder manueller bestätigter Eingabe | IMPLEMENTED | Refresh nur nach Nutzerklick |
| B405 | KGV | `=I398/E403` | Preis je Gewinn je Aktie | market_cap, net_income | market_cap / net_income | IMPLEMENTED | Äquivalent bei konsistenter Aktienzahlbasis |
| B411 | KBV | `=I398/E409` | Preis je Buchwert je Aktie | market_cap, shareholders_equity | market_cap / shareholders_equity | IMPLEMENTED | Equity <= 0: nicht aussagekräftig |
| B417 | KCV | `=I398/E415` | Preis je operativem Cashflow je Aktie | market_cap, operating_cash_flow | market_cap / operating_cash_flow | IMPLEMENTED | OCF <= 0: nicht aussagekräftig |
| N424 | Marktwert Eigenkapital | `=N422*N421` | Marktkapitalisierung | price, shares_outstanding | price * shares_outstanding | IMPLEMENTED | Aktienzahl darf nicht geraten werden |
| N428 | Enterprise Value | `=N424+N425-N426` | Unternehmenswert für Eigen- und Fremdkapitalgeber | market_cap, net_debt | market_cap + net_debt | IMPLEMENTED | EV bleibt Review Required, wenn Net Debt fehlt |
| B427 | EV/EBITDA | `=N428/(F12+F70)` | EV relativ zu EBITDA | enterprise_value, ebitda | enterprise_value / ebitda | IMPLEMENTED | EBITDA bleibt intern: operating_income + D&A |
| B441 | EV/EBIT | `=N428/F12` | EV relativ zum operativen Ergebnis | enterprise_value, operating_income | enterprise_value / operating_income | IMPLEMENTED | EV erforderlich |
| E454 | Entity FCF | `=((E95+L183-E79*-1)+(F95+M183-F79*-1))/2` | Entity-Cashflow für EV/FCF | operating_cash_flow, interest_expense, capital_expenditures | operating_cash_flow + interest_expense - capital_expenditures | IMPLEMENTED_WITH_GATE | Wenn interest_expense fehlt: EV/FCF nicht verfügbar |
| B454 | EV/FCF | `=N428/E454` | EV relativ zu Entity-FCF | enterprise_value, entity_free_cash_flow_excel_book | enterprise_value / entity_free_cash_flow_excel_book | IMPLEMENTED | Verwendet niemals Equity-FCF |
| B466 | EV/Sales | `=N428/F2` | EV relativ zum Umsatz | enterprise_value, revenue | enterprise_value / revenue | IMPLEMENTED | Höhere Werte können bei hohen Margen plausibler sein |

## DCF-Verfahren - Equity-Methode

| Excel-Zelle | Excel-Bezeichnung | Excel-Formel | Fachliche Bedeutung | App-Backend-Input | Neue App-Formel | Status | Abweichung / Hinweis |
|---|---|---|---|---|---|---|---|
| A480-A482 | DCF-Schritte | Text | Vier sichtbare Hauptschritte | UI layout | Owner Earnings, Diskontierung, Ewige Rente, Fairer Aktienkurs | IMPLEMENTED | Sichtbare Struktur in `pages/3_Analyse.py` |
| B506:F506 | Sachinvestitionen | `=(B79*-1)+(B83*-1)` ff. | Owner-Earnings-CAPEX | capital_expenditures, intangible_purchases | capital_expenditures + intangible_purchases | IMPLEMENTED_WITH_GATE | Fehlende intangible_purchases werden nicht als 0 gesetzt |
| B515:F515 | Operating Working Capital | `=B32+B31-B46` ff. | Operativ gebundenes Kapital | inventory, accounts_receivable, accounts_payable | inventory + AR - AP | IMPLEMENTED | Getrennt von allgemeinem Working Capital |
| C517:P517 | Veränderung OWC | `=C515-B515` ff. | Working-Capital-Bindung im Jahr | operating_working_capital current/previous | OWC(t) - OWC(t-1) | IMPLEMENTED | Fehlendes Vorjahr sperrt Ergebnis |
| C520:P520 | Owner Earnings | `=C500+C511-C506-C517` ff. | Eigentümerertrag | net_income, D&A, owner_earnings_capex, ΔOWC | net_income + D&A - owner_capex - ΔOWC | IMPLEMENTED | Eigene Methodik, überschreibt FCF nicht |
| B532 | Risikoaufschlag | `=1/B531` | Renditeaufschlag aus fairem KGV | fair_pe | 1 / fair_pe | IMPLEMENTED | fair_pe muss aus Multiplikatorenmethode oder manueller Annahme kommen |
| B535 | Eigenkapitalkosten | `=B533+B532+B534` | Diskontierungszins | risk_free_rate, fair_pe, minimum_return_addon | risk_free + 1/fair_pe + addon | IMPLEMENTED | Mindestverzinsung 7 % via Addon |
| G539:P539 | Barwert Owner Earnings | `=G520/((1+$B$535)^G537)` ff. | Barwert der jährlichen Owner Earnings | forecast owner_earnings, discount_rate | owner_earnings / (1+r)^n | IMPLEMENTED | Prognosequelle noch getrennt zu prüfen |
| B553 | Terminal Value | `=(P520*(1+B552))/(B535-B552)` | Ewige Rente | last_owner_earnings, terminal_growth, discount_rate | OE_n*(1+g)/(r-g) | IMPLEMENTED | g < r Gate |
| B554 | Barwert Terminal Value | `=B553/(1+B535)^10` | heutiger Wert der ewigen Rente | terminal_value, discount_rate, n | terminal_value/(1+r)^n | IMPLEMENTED | n = Planjahre |
| B560 | Wert des Eigenkapitals | `=B554+B540` | Equity Value | PV Owner Earnings, PV Terminal Value | Summe PV OE + PV TV | IMPLEMENTED | Keine Net-Debt-Anpassung in Equity-Methode |
| B562 | Fairer Aktienkurs | `=B560/B559` | Fair Value per Share | equity_value, shares_outstanding | equity_value / shares | IMPLEMENTED | Aktienzahl erforderlich |
| B564 | Fairer Aktienkurs nach MoS | `=B562/1*(1-B563)` | Sicherheitsabschlag | fair_value, margin_of_safety | fair_value*(1-MoS) | IMPLEMENTED | Keine BUY/HOLD/SELL-Ableitung |
| B568 | Bewertung | `=1-(1/B567*B564)` | Abstand zum Kurs | fair_after_mos, market_price | 1 - fair_after_mos / market_price | IMPLEMENTED | Deutsch als Bewertungslücke |
| L569:N571 | Simulation | `MAX/MIN/AVERAGE/STDEV.P` | Simulationsauswertung | VBA/Simulation | nicht implementiert | SIMULATION_METHOD_REVIEW_REQUIRED | Makro-/Simulationslogik nicht eindeutig rekonstruiert; keine Monte-Carlo-Erfindung |

## Multiplikatorenmethode

| Excel-Zelle | Excel-Bezeichnung | Excel-Formel | Fachliche Bedeutung | App-Backend-Input | Neue App-Formel | Status | Abweichung / Hinweis |
|---|---|---|---|---|---|---|---|
| B583 | Sockel-KGV | Eingabewert 7.5 | Ausgangs-KGV | manual/base_pe | base_pe | IMPLEMENTED | Orientierungswert, Nutzerprüfung |
| B594 | Finanzielle Stabilität | Eingabewert 2 | Stabilitätsaufschlag | manual/stability | financial_stability_addon | IMPLEMENTED | Automatische Kennzahlen ergänzend sichtbar, Aufschlag manuell |
| B605/B610/B615/B620/B624 | Porter-Punkte | Eingabewerte | Marktposition | manual Porter scores | Summe fünf Kräfte | IMPLEMENTED | Keine automatische KI-Wertung |
| B626 | Summe Porter Punkte | `=B605+B610+B615+B620+B624` | Gesamtpunktzahl Marktposition | Porter scores | sum(scores) | IMPLEMENTED | Persistenzpfad über manuelle Buchannahmen vorgesehen |
| B627 | KGV-Aufschlag Marktposition | Eingabewert 2.2 | Aufschlag Marktposition | manual | market_position_addon | IMPLEMENTED | Keine erfundene Formel |
| B647 | Multiplikator Rentabilität | Eingabewert 2 | Rentabilitätsmultiplikator | manual | profitability_multiplier | IMPLEMENTED | Excel multipliziert Marktposition damit |
| B669 | Wachstum | Eingabewert 0.8 | Wachstumsaufschlag | manual/estimate/history | growth_addon | IMPLEMENTED | Forecastquelle sichtbar machen |
| B676 | Individualität | Eingabewert 2 | Qualitativer Aufschlag | manual note | individuality_addon | IMPLEMENTED | Begründung erforderlich |
| B682 | Marktposition und Rentabilität | `=B627*B647` | kombinierter Aufschlag | market_position_addon, profitability_multiplier | multiplication | IMPLEMENTED | Exakt nach Excel |
| B685 | Faires KGV | `=SUM(B680:B684)` | Summe Komponenten | all components | base + stability + combined + growth + individuality | IMPLEMENTED | Kein Business-Quality-Ersatz |
| B698 | Prognose-EPS | `=B695/B696` | Gewinn je Aktie | forecast_net_income, shares | forecast_net_income / shares | IMPLEMENTED | Jahresforecast erforderlich |
| B700 | Innerer Wert | `=B685*B695` | Excel-Zwischengröße | fair_pe, forecast_net_income | dokumentiert | EXCEL_FORMULA_REVIEW_REQUIRED | Excel-Zwischengröße wirkt skaleninkonsistent für Unternehmenswert; fairer Preis nutzt B701 |
| B701 | Fairer Preis je Aktie | `=B700/B696` | fairer Aktienwert | fair_pe, forecast_eps | fair_pe * forecast_eps | IMPLEMENTED | Algebraisch äquivalent zu B685*(B695/B696) |
