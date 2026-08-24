# FINANCIAL WORKSHEET + MISSING DATA SEARCH AUDIT

Status: GO - FINANZDATEN-ARBEITSBLATT UND MISSING-DATA-SUCHE V1

## Scope

Phase 9D wurde als UI-/Workflow-Schicht umgesetzt. Die eingefrorenen Engines fuer Financial Data Pipeline V1, Calculation Engine V1, Historical Analysis Engine V1, Business Quality Engine V1, Market Data und Valuation wurden nicht fachlich umgebaut.

## Ergebnis

- Finanzdaten sind auf der Seite `Finanzdaten` primaer als Excel-artiges Arbeitsblatt sichtbar.
- Die Tabellen sind in `Gewinn- und Verlustrechnung`, `Bilanz` und `Cashflow` gruppiert.
- Die Jahre sind horizontal angeordnet und koennen auf `5 Jahre`, `10 Jahre` oder `Alle` umgeschaltet werden.
- Jede Zelle zeigt einen nutzerlesbaren Status statt technischer Codes.
- Offene Zellen koennen direkt ausgewaehlt werden.
- Fehlende oder pruefpflichtige Zellen bieten direkt `Fehlenden Wert suchen` bzw. `Kandidaten suchen`.
- Kandidaten werden mit Wert, Quelle, Provider Field, Filing Date, Semantic-Status und Begruendung angezeigt.
- Manuelle Overrides werden als `manual_override` gespeichert und gewinnen nur in Preferred Data.
- Importierte Originalwerte bleiben unveraendert erhalten.
- Overrides koennen entfernt werden; danach greift wieder der automatisch bevorzugte Wert.

## Zellstatus

- `AUTOMATISCH_BESTAETIGT` -> `✓ automatisch`
- `PRUEFUNG_ERFORDERLICH` -> `⚠ prüfen`
- `MANUELL_BESTAETIGT` -> `✎ manuell`
- `MANUELL_UEBERSCHRIEBEN` -> `✎ überschrieben`
- `KANDIDAT_GEFUNDEN` -> `? Kandidat`
- `FEHLT` -> `— fehlt`
- `NICHT_SEPARAT_BERICHTET` -> `n/a nicht separat berichtet`

## Suchstufen

Die UI startet keine neue Datenpipeline. Sie nutzt die vorhandene Infrastruktur:

1. bereits importierte strukturierte Primaerdaten
2. SEC CompanyFacts / vorhandene alternative Facts
3. SEC Original Filing / XBRL ueber vorhandene Importstufen
4. SEC Tabellen-/Text-Fallback ueber `sync_sec_history_text_candidates(...)`
5. ESEF / offizielle Jahresberichte ueber bestehenden Source Router
6. externe Fallback-Provider nur ueber bestehende Nutzerfreigabe
7. manuelle Eingabe, standardmaessig mit Quelle `Aktienfinder`

Diagnostics-CSV wird nicht als Produktquelle verwendet.

## Short-Term-Debt-Policy

Interne Definition bleibt:

Kurzfristige zinstragende Finanzschulden mit Faelligkeit innerhalb von 12 Monaten, inklusive current portion of long-term debt, ohne Trade Payables und ohne Leasingverbindlichkeiten.

Akzeptierte Kandidatenfelder:

- `DebtCurrent`
- `ShortTermBorrowings`
- `CurrentBorrowings`
- `LongTermDebtCurrent`
- `CurrentPortionOfLongTermDebt`
- `CurrentPortionOfLongtermBorrowings`
- passende Borrowings-Felder

Explizit abgelehnt:

- `AccountsPayable`
- `CurrentLiabilities` / `LiabilitiesCurrent`
- `LeaseLiabilityCurrent`
- Trade-Payables- und Lease-Liability-Felder

## ASML Regression

Lokaler Stand: ASML Analyse `id=1`, Stichtag `2026-08-23`, Revision `1`.

Gepruefte Zellen:

| Jahr | Metrik | Wert | Waehrung | Quelle | Provider Field | Status | Grund |
|---:|---|---:|---|---|---|---|---|
| 2023 | Kurzfristige Finanzschulden | 100000.00000000 | EUR | sec_companyfacts | aggregation:us-gaap:LongTermDebtCurrent | REVIEW_REQUIRED | Das Feld ist ein offizieller Kandidat, aber nicht in der versionierten Safe-Standard-Mapping-Registry freigegeben. |
| 2024 | Kurzfristige Finanzschulden | 1010300000.00000000 | EUR | sec_companyfacts | aggregation:us-gaap:LongTermDebtCurrent | REVIEW_REQUIRED | Das Feld ist ein offizieller Kandidat, aber nicht in der versionierten Safe-Standard-Mapping-Registry freigegeben. |
| 2025 | Kurzfristige Finanzschulden | 1681900000.00000000 | EUR | sec_companyfacts | aggregation:us-gaap:LongTermDebtCurrent | REVIEW_REQUIRED | Das Feld ist ein offizieller Kandidat, aber nicht in der versionierten Safe-Standard-Mapping-Registry freigegeben. |

Damit sieht der Nutzer direkt:

`Finanzdaten -> Bilanz -> Kurzfristige Finanzschulden -> 2025 -> prüfen -> Kandidaten suchen / bestätigen / überschreiben`

## Tests

Neue Tests:

- Financial Worksheet gruppiert GuV/Bilanz/Cashflow korrekt.
- 5Y/10Y/Alle funktioniert.
- Fehlende Zellen und Review-Zellen sind als offene Zellen auffindbar.
- Override persistiert.
- Originalfact bleibt unveraendert.
- Override entfernen stellt automatischen Wert wieder her.
- Structured safe candidate ist direkt verwendbar.
- Semantic-review candidate wird nicht automatisch freigegeben.
- Multiple/no-candidate-Verhalten ist ueber Kandidatenliste/manuelle Eingabe abgedeckt.
- Short-Term-Debt Regression: `DebtCurrent` erlaubt, `CurrentPortionOfLongTermDebt` Kandidat, `AccountsPayable`, `CurrentLiabilities` und `LeaseLiabilityCurrent` abgelehnt.

## Entscheidung

GO - FINANZDATEN-ARBEITSBLATT UND MISSING-DATA-SUCHE V1
