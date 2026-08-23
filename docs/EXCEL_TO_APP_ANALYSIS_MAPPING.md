# Excel-to-App Analysis Mapping

Quelle: `Bewertung Kone Aufzüge.xlsm`, Blatt `Krones`.

Die Excel-Datei wurde nur als fachliche Reihenfolge, Beschriftungs- und Erklärvorlage verwendet. Formeln aus der Excel-Datei wurden nicht in die eingefrorenen Engines übernommen. Die App zeigt ausschließlich Werte aus den freigegebenen Financial-Data-, Calculation-, Historical-, Business-Quality-, Market-Data-, Assumption- und Valuation-Schichten.

## Zielbild der Analyse-Seite

| Reihenfolge | App-Abschnitt | Excel-Bezug | Umsetzung |
|---:|---|---|---|
| 1 | Unternehmensüberblick | Aktuelle Daten | Header mit Unternehmen, Ticker, Stichtag, Kurs, Währungen und Historie |
| 2 | Gewinn- und Verlustrechnung | Zeile 1 ff. | Umsatz, Bruttoergebnis, Betriebsergebnis, Jahresüberschuss, EBITDA |
| 3 | Bilanz | Zeile 24 ff. | Liquide Mittel, Forderungen, Vorräte, Sachanlagen, Goodwill, Vermögen, Eigenkapital und Schulden |
| 4 | Cashflow | Zeile 67 ff. | Operativer Cashflow, Investitionen, FCF, Dividendenzahlungen |
| 5 | Ertrag und Rentabilität | Zeile 15, 39, 45 ff. | Margen, ROE, ROA und Cashflow-Margen |
| 6 | Finanzielle Stabilität | Zeile 57 ff. | Eigenkapitalquote, Cash Ratio, Quick Ratio, Current Ratio |
| 7 | Verschuldung | Zeile 189 ff. | Schuldenquote, Debt/Equity, Net Debt, Net Debt/EBITDA |
| 8 | Kapitalbindung / Working Capital | Zeile 300 ff. | Working Capital, Forderungslaufzeit, Kreditorenlaufzeit, Vorratskennzahlen |
| 9 | Cashflow-Qualität / Kapitalallokation | Zeile 251, 272, 283, 290 | OCF-Marge, FCF-Marge, Capex-Quote, Dividendenzahlungen |
| 10 | Bewertungskennzahlen | Zeile 397 ff. | Market Cap, EV, KGV, P/FCF, EV/EBIT, EV/EBITDA |
| 11 | DCF-Bewertung | Zeile 475 ff. | FCF-Basis, Wachstum, Diskontierungszins, Terminal Growth, Szenarien |
| 12 | Multiplikatoren-/Qualitätsbetrachtung | Zeile 572 ff. | Unternehmensqualität und Datenvertrauen getrennt von Bewertung |
| 13 | Zusammenfassung | Schlusslogik der Vorlage | Offene Prüfungen, Bewertungsbandbreite, keine Handlungsempfehlung |

## Unterstützte Kennzahlen

| Excel-Bezeichnung | App-Label | Backend-Key | Status | Hinweise |
|---|---|---|---|---|
| Umsatz | Umsatz | `revenue` | SUPPORTED | Primärwert aus Calculation-Ready-Fakten |
| Bruttoergebnis | Bruttoergebnis | `gross_profit` | SUPPORTED | Wird nur angezeigt, wenn separat verfügbar |
| Betriebsergebnis | Betriebsergebnis | `operating_income` | SUPPORTED | EBIT-nahe Operating-Income-Logik aus Frozen Engine |
| Jahresüberschuss | Jahresüberschuss | `net_income` | SUPPORTED | Vorzeichen bleibt unverändert |
| EBIT/EBITDA | EBITDA | `ebitda` | SUPPORTED | Interne Formel bleibt unverändert: Operating Income + D&A |
| Bilanzsumme | Gesamtvermögen | `total_assets` | SUPPORTED | Primärwert aus Bilanz |
| Eigenkapital | Eigenkapital | `shareholders_equity` | SUPPORTED | Primärwert aus Bilanz |
| Liquidität | Liquide Mittel | `cash_and_equivalents` | SUPPORTED | Cash und cash equivalents |
| Vorräte | Vorräte | `inventory` | SUPPORTED/CONDITIONAL | Nicht separat berichtete Werte bleiben `Nicht verfügbar` |
| Kurzfristige Finanzschulden | Kurzfristige Finanzschulden | `short_term_debt` | SUPPORTED | Review-Policy bleibt erhalten |
| Langfristige Finanzschulden | Langfristige Finanzschulden | `long_term_debt` | SUPPORTED | Review-Policy bleibt erhalten |
| Operativer Cashflow | Operativer Cashflow | `operating_cash_flow` | SUPPORTED | Primärwert aus Cashflow-Statement |
| Investitionen | Sachinvestitionen | `capital_expenditures` | SUPPORTED | Vorzeichenkonvention der Engine bleibt maßgeblich |
| Free Cash Flow | Freier Cashflow (FCF) | `free_cash_flow` | SUPPORTED | Calculation Engine V1 |
| ROE | Eigenkapitalrendite (ROE) | `return_on_equity` | SUPPORTED | Als Dezimalwert gespeichert, deutsch als Prozent dargestellt |
| ROA | Vermögensrendite (ROA) | `return_on_assets` | SUPPORTED | Als Prozent dargestellt |
| Umsatzrendite | Nettomarge | `net_margin` | SUPPORTED | Als Prozent dargestellt |
| Eigenkapitalquote | Eigenkapitalquote | `equity_ratio` | SUPPORTED | Finanzielle Stabilität |
| Cash Ratio | Liquidität 1. Grades | `cash_ratio` | SUPPORTED | Kein Null-Imputing |
| Quick Ratio | Liquidität 2. Grades | `quick_ratio` | SUPPORTED | Kein Null-Imputing |
| Current Ratio | Liquidität 3. Grades | `current_ratio` | SUPPORTED | Kein Null-Imputing |
| Debt to Equity Ratio | Debt to Equity | `debt_to_equity` | SUPPORTED | Kapitalstruktur |
| Relative Verschuldung | Nettoverschuldung / EBITDA | `net_debt_to_ebitda` | SUPPORTED | Bei fehlendem Net Debt nicht verfügbar |
| Capex / Umsatz bzw. Cashflow | Sachinvestitionen / operativer Cashflow | `capex_ratio` | SUPPORTED | Cashflow-Qualität |
| KGV | Kurs-Gewinn-Verhältnis (KGV) | `latest_fy_pe` | SUPPORTED | Valuation Engine V1 |
| EV/EBITDA | EV / EBITDA | `latest_fy_ev_ebitda` | SUPPORTED | Nur mit calculation-ready EV |
| EV/EBIT | EV / EBIT | `latest_fy_ev_ebit` | SUPPORTED | Nur mit calculation-ready EV |
| DCF-Annahmen | FCF, Wachstum, Diskontierungszins, Terminal Growth | `base_fcf`, `growth_rate`, `discount_rate`, `terminal_growth_rate` | SUPPORTED | Annahmen bleiben prüfbar |

## Bewusst nicht oder nur teilweise umgesetzt

| Excel-Bezeichnung | App-Darstellung | Status | Begründung |
|---|---|---|---|
| Anlagendeckung | Noch nicht in der aktuellen Engine verfügbar | NOT_CURRENTLY_IMPLEMENTED | Keine freigegebene Calculation-Engine-Kennzahl vorhanden |
| Long-Term Debt to Equity | Noch nicht in der aktuellen Engine verfügbar | NOT_CURRENTLY_IMPLEMENTED | Keine neue Verschuldungslogik in dieser UX-Phase |
| Short-Term Debt to Equity | Noch nicht in der aktuellen Engine verfügbar | NOT_CURRENTLY_IMPLEMENTED | Keine neue Verschuldungslogik in dieser UX-Phase |
| Zinsdeckungsgrad | Noch nicht in der aktuellen Engine verfügbar | NOT_CURRENTLY_IMPLEMENTED | Zinsaufwand ist nicht als geprüfter Calculation-Ready-Input freigegeben |
| Schulden je Aktie | Noch nicht in der aktuellen Engine verfügbar | NOT_CURRENTLY_IMPLEMENTED | Pro-Aktie-Schuldenlogik nicht Teil der eingefrorenen Engines |
| Netto-Cash je Aktie | Noch nicht in der aktuellen Engine verfügbar | NOT_CURRENTLY_IMPLEMENTED | Pro-Aktie-Net-Cash-Logik nicht Teil der eingefrorenen Engines |
| KBV | Noch nicht in der aktuellen Engine verfügbar | NOT_CURRENTLY_IMPLEMENTED | Kein freigegebener Multiples-Output in Valuation Engine V1 |
| KCV | Noch nicht in der aktuellen Engine verfügbar | NOT_CURRENTLY_IMPLEMENTED | Kein freigegebener Multiples-Output in Valuation Engine V1 |
| EV/Umsatz | Noch nicht in der aktuellen Engine verfügbar | NOT_CURRENTLY_IMPLEMENTED | Kein freigegebener Multiples-Output in Valuation Engine V1 |
| EV/FCF | Noch nicht in der aktuellen Engine verfügbar | NOT_CURRENTLY_IMPLEMENTED | Kein freigegebener Multiples-Output in Valuation Engine V1 |

## UI-Regeln

- Primäre Oberfläche zeigt deutsche Labels und keine internen Statuscodes.
- Interne Codes bleiben nur im Expander `Technische Details anzeigen` sichtbar.
- Fehlende Werte werden als `Nicht verfügbar` dargestellt und niemals still als `0`.
- Jeder sichtbare Analysepunkt verweist auf einen zentralen Info-Katalog.
- Review-Zustände werden als prüfbare Hinweise dargestellt, nicht als technischer App-Fehler.
- Die Reihenfolge ist linear und orientiert sich an der Excel-/Buchlogik.
