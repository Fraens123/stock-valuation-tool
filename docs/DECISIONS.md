# Decisions Log

## D-001 — Streamlit als Ziel-UI
**Status:** Accepted

Excel bleibt fachliche Referenz; Python wird Daten-, Berechnungs- und Persistenzkern.

## D-002 — ASML als Referenzunternehmen
**Status:** Accepted

ASML Holding N.V. (`ASML.AS`) wird für Entwicklung, Vergleich und Plausibilisierung verwendet.

## D-003 — Snapshot-/Revisionsmodell
**Status:** Accepted

Abgeschlossene Analysen werden nicht überschrieben. Aktualisieren erzeugt eine neue Revision.

## D-004 — SQLite V1
**Status:** Accepted

Lokale Persistenz über SQLite; Datenzugriff wird so gekapselt, dass PostgreSQL später möglich bleibt.

## D-005 — Aktienfinder manuell
**Status:** Accepted

Keine Abhängigkeit von einer undokumentierten API. Aktienfinder erhält eine zentrale manuelle Eingabemaske.

## D-006 — EODHD als erster API-Kandidat
**Status:** Superseded after Phase-2 live test

Der kostenlose EODHD-Key ist gültig, der Fundamentals-v1.1-Endpunkt für `ASML.AS` liefert jedoch HTTP 403. Ein kostenpflichtiger Fundamentals-Tarif wird vorerst nicht gekauft. Der Adapter bleibt als optionaler späterer Fallback/Cross-Check erhalten. Alpha Vantage wird stattdessen als automatischer V1-Kandidat feldweise gegen ASML-Primärquellen validiert.

## D-007 — Equity-DCF zuerst
**Status:** Accepted

Zuerst bestehende Owner-Earnings-/Equity-DCF-Logik reproduzieren; Entity-DCF später als Cross-Check.

## D-008 — Analystenschätzungen nur kurzfristig dominierend
**Status:** Accepted

Jahre 1–3 können durch Guidance/Konsens stark verankert werden; langfristig eigene fundamentale Annahmen und Fade.

## D-009 — Risiko-KGV getrennt prüfen
**Status:** Proposed / Book validation required

Ein risikoorientiertes KGV für den DCF-Diskontsatz soll vom vollständigen wachstumsabhängigen Fair-KGV getrennt geprüft werden, um Doppelzählung zu verhindern.

## D-010 — PDF aus Snapshot
**Status:** Accepted

Reports dürfen nur gespeicherte Snapshot-Daten verwenden und müssen historische Analysen reproduzierbar darstellen.

## D-011 — Automatische Provider werden feldweise freigegeben
**Status:** Accepted

Ein Datenprovider wird nicht pauschal als korrekt betrachtet. Für den ASML-Referenzfall entscheidet der Primärquellencheck je internem Rohdatenfeld zwischen `approved`, `review` und `blocked`. FAIL/MISSING-Felder eines API-Providers dürfen nicht ungeprüft von Downstream-Kennzahlen verwendet werden.

Offizielle Primärquellenwerte dürfen als **eigene, separat gespeicherte Quelle** ergänzt werden. Sie überschreiben oder löschen die ursprüngliche API-Zahl nicht; die Provenienz beider Werte bleibt erhalten.

## D-012 — ASML EBIT-Marge verwendet validiertes Income from operations
**Status:** Accepted for ASML reference case only

Für die erste Phase-3A-Kennzahl wird bei ASML das gegen die Primärquelle validierte Feld `operating_income` (`Income from operations`) als operative EBIT-Basis verwendet und durch `revenue` dividiert. Diese provider-/unternehmensspezifische Zuordnung ist keine universelle Definition für andere Unternehmen; dort muss die EBIT-Semantik erneut geprüft werden.

## D-013 — Hybride Quellenstrategie für Fundamentaldaten
**Status:** Accepted; Prioritätsdetails durch D-016 präzisiert

V1 verwendet keine Annahme, dass ein einzelner Drittanbieter sämtliche Finanzzeilen korrekt normalisiert.

Für ASML werden die offiziellen 2025-US-GAAP-Financial-Statements als eigene Quelle `asml_primary` gespeichert. Alpha-Vantage-Werte bleiben parallel im Snapshot. Der Daten-Gate bevorzugt für dasselbe Feld/Jahr `asml_primary`, ohne den Fallback-Wert zu löschen.

Die breite historische API-Serie wird nicht rückwirkend durch einen pauschalen Skalierungs- oder Korrekturfaktor verändert. Insbesondere werden die ASML-Cashflow-Abweichungen von Alpha Vantage nicht mathematisch „repariert“.

## D-014 — ASML ist Referenzfall, nicht Import-Sonderweg
**Status:** Accepted

Neue Unternehmen müssen ohne Codeänderung angelegt und importiert werden können. Unternehmenssuche und Fundamentals-Ticker werden providerbezogen gespeichert. `Company.ticker` wird nicht als universeller Identifier missbraucht.

Unternehmensidentität:

1. ISIN, wenn verfügbar;
2. sonst Ticker + Börse/Region.

Ein gleicher Ticker an zwei Börsen darf nicht automatisch zu einem Unternehmen zusammengeführt werden.

## D-015 — Generische Primärquellenadapter statt Unternehmensparser
**Status:** Accepted

Der ASML-XLSX-Parser bleibt ein Referenzadapter. Für breite Abdeckung werden generische regulatorische Quellen bevorzugt:

1. SEC EDGAR Company Facts/XBRL für SEC-reporting Unternehmen (`sec_companyfacts`),
2. europäische ESEF/iXBRL-Quellen für IFRS-Emittenten,
3. generischer IR-Dokumentimport als Fallback.

`sec_companyfacts` ist als offizielle Primärquelle in der zentralen Source-Resolution höher priorisiert als Alpha Vantage. Alpha-Vantage-Daten bleiben parallel gespeichert und auditierbar.

## D-016 — Preferred Data ist die einzige Berechnungsbasis
**Status:** Accepted

Die Anwendung trennt ab sofort zwei Ebenen:

1. **Source Resolution:** Welcher gespeicherte Wert ist für ein Feld/Jahr der bevorzugte Wert?
2. **Calculation Readiness:** Darf dieser bevorzugte Wert tatsächlich in Kennzahlen und später in Bewertungen eingehen?

Quellenpriorität bei identischem Feld/Jahr:

1. vom Nutzer bestätigter `manual_override`,
2. eindeutig gemappte offizielle Primärquelle (`asml_primary`, `sec_companyfacts`, ESEF/iXBRL),
3. Alpha Vantage als Provider-Fallback,
4. weitere Provider-Fallbacks.

Ein Provider-Fallback wird **nicht allein durch seine Position in der Quellenpriorität berechnungsbereit**. Berechnungsbereit sind nur:

- bestätigte Overrides,
- eindeutig gemappte Primärquellenwerte,
- Providerwerte mit explizitem Primärquellen-PASS aus der ChatGPT-Dateiprüfung,
- der bestehende ASML-Referenzgate als Legacy-Primärquellenvalidierung.

`WARN`, `FAIL`, `UNKLAR`, veraltete Reviews und ungeprüfte Providerwerte bleiben gespeichert, sind aber für Downstream-Berechnungen gesperrt.

Fertiges Provider-EBITDA ist kein autoritativer Raw Input. EBITDA wird für Kennzahlen aus freigegebenem EBIT und sauber definiertem D&A selbst berechnet. Bei Unternehmen außerhalb des ASML-Referenzfalls wird `operating_income` nicht still mit EBIT gleichgesetzt; dort ist das freigegebene interne `ebit` die EBIT-Basis.

Interne Feldsemantik wird zentral dokumentiert. Insbesondere:

- `ppe_net` schließt separat ausgewiesene Operating-Lease-ROU-Assets aus,
- `short_term_debt` umfasst zinstragende Schulden mit Fälligkeit <= 12 Monate einschließlich Current Portion of Long-Term Debt,
- `depreciation_amortization` umfasst reine Abschreibung + Amortisation und nicht automatisch zusätzliche `and other`-Posten.
