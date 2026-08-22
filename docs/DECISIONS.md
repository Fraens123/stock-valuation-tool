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
**Status:** Accepted

V1 verwendet keine Annahme, dass ein einzelner Drittanbieter sämtliche Finanzzeilen korrekt normalisiert.

Quellenpriorität für einen konkreten Rohdatenwert:

1. offizielle Unternehmens-/Primärquelle, wenn deterministisch importiert und fachlich eindeutig zugeordnet;
2. feldweise validierter API-Provider, aktuell Alpha Vantage;
3. weitere API-/Cross-Check-Quelle;
4. expliziter manueller Override, wenn die Anwendung dies für den jeweiligen Datentyp vorsieht.

Für ASML werden die offiziellen 2025-US-GAAP-Financial-Statements als eigene Quelle `asml_primary` gespeichert. Alpha-Vantage-Werte bleiben parallel im Snapshot. Der Daten-Gate bevorzugt für dasselbe Feld/Jahr `asml_primary`, ohne den Fallback-Wert zu löschen.

Die breite historische API-Serie wird nicht rückwirkend durch einen pauschalen Skalierungs- oder Korrekturfaktor verändert. Insbesondere werden die ASML-Cashflow-Abweichungen von Alpha Vantage nicht mathematisch „repariert“.
