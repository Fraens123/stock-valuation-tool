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
**Status:** Proposed / Validate in Phase 2

Abdeckung, Datenqualität und Tarif werden an ASML geprüft, bevor die Entscheidung final wird.

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
