# Roadmap

Diese Roadmap ist die verbindliche Entwicklungsreihenfolge. `AGENTS.md` enthält die dauerhaften Regeln, `CURRENT_TASK.md` den aktuell zu bearbeitenden Block.

## Statusübersicht

- **Phase 0 – Application Foundation:** ✅ implementiert
- **Phase 1 – Excel-/Buch-Spezifikation:** ✅ weitgehend abgeschlossen; einzelne Buchdefinitionen bleiben bewusst als offene Methodikfragen markiert
- **Phase 2 – Datenversorgung:** 🟡 in Arbeit; Code steht, echter ASML/EODHD-Live-Test benötigt lokalen API-Key
- **Phase 3 ff.:** noch nicht beginnen, bevor die Datenpipeline an ASML validiert ist

---

# Phase 0 — Application Foundation ✅

## 0.1 Projektgrundlage
- [x] Repository
- [x] `AGENTS.md`
- [x] `CURRENT_TASK.md`
- [x] Python-Projektstruktur
- [x] `.gitignore`, `.env.example`, `pyproject.toml`
- [x] pytest / GitHub-Actions-Grundlage

## 0.2 Unternehmen
- [x] Company-Domainmodell
- [x] Name, Ticker, ISIN, Börse, Land, Währung, Sektor, Provider-Symbol
- [x] lokales Suchinterface
- [x] ASML als Referenzunternehmen
- [ ] externe Symbols-/Listing-Suche mit Provider nach Live-Test
- [ ] Mehrfachlistings später als eigene Entität, falls erforderlich

## 0.3 Analyse-Lifecycle
- [x] Analyse erstellen
- [x] Analyse öffnen/bearbeiten
- [x] Draft / In Progress / Completed / Archived
- [x] Revisionsnummer
- [x] vorherige Revision verknüpfen
- [x] abgeschlossene Revision einfrieren
- [x] neue Revision aus abgeschlossener Analyse
- [x] qualitative Einschätzungen optional übernehmen
- [x] übernommene qualitative Einschätzungen als `needs_review` markieren
- [x] alte Finanz-/Marktdaten nicht in neue Revision kopieren

## 0.4 Persistenz
- [x] SQLite V1
- [x] SQLAlchemy Models
- [x] Service Layer
- [x] DB-Dateien in `.gitignore`
- [x] Snapshot-Grundmodell
- [ ] Migrationsstrategie vor erstem stabilen Release (Alembic oder kontrollierte lokale Migration)

## 0.5 Vergleich und PDF-Grundlage
- [x] zwei Revisionen desselben Unternehmens vergleichen
- [x] Fundamentaldaten-Diff
- [x] Estimates-/Guidance-Diff
- [x] Bewertungsannahmen-/Ergebnis-Diff
- [x] qualitative Einschätzungen-Diff
- [x] erster reproduzierbarer PDF-Snapshot
- [x] alter Report verwendet keine Live-Daten

**Definition of Done Phase 0:** erfüllt.

---

# Phase 1 — Fachliche Spezifikation / Excel- und Buch-Mapping ✅/🟡

## 1.1 Excel-Inventarisierung
- [x] bestehendes Excel von oben nach unten analysiert
- [x] Rohdatenzeilen dokumentiert
- [x] Excel-Formeln der Kernkennzahlen dokumentiert
- [x] DCF-Logik dokumentiert
- [x] Fair-KGV-/Multiplikatorenlogik dokumentiert
- [x] VBA-Szenarioidee dokumentiert
- [x] Kennzahlen klassifiziert: keep / add / adjust / special / verify
- [x] methodische Schwächen des Alt-Excel explizit markiert

Siehe `docs/PHASE_1_METRIC_INVENTORY.md`.

## 1.2 Kennzahlen- und Wissenskatalog
- [x] `metrics.yaml` als zentrales Kennzahlenwissen
- [x] deutsche + englische Überschriften
- [x] Definition
- [x] Ziel- und Excel-Formel
- [x] Bedeutung
- [x] Interpretation
- [x] Fallstricke
- [x] verwandte Kennzahlen
- [x] Excel-Zellbereiche
- [x] Kindle-Seiten aus Nutzer-Screenshots
- [x] `ⓘ`-Komponente an neues Schema angepasst
- [x] Tests für Katalogschema

## 1.3 Buchstruktur
- [x] Kapitel 2 Ertrag/Rentabilität
- [x] Kapitel 3 Finanzielle Stabilität
- [x] Kapitel 4 Working Capital
- [x] Kapitel 5 Geschäftsmodell
- [x] Kapitel 6 Ausschüttung
- [x] Kapitel 7 Bewertungskennzahlen
- [x] Kapitel 8 Bewertung
- [x] Kapitel 9 Margin of Safety / Investmententscheidung
- [ ] Kapitel 1 ergänzen, sobald relevante Kindle-Seiten vorliegen
- [ ] einzelne exakte Buchformeln auf den in `METHODOLOGY_OPEN_QUESTIONS.md` markierten Seiten verifizieren

## 1.4 Qualitative Unternehmensanalyse
- [x] Kapitel-5-Struktur in `qualitative.yaml`
- [x] Kompetenzbereich
- [x] Charakteristika
- [x] Rahmenbedingungen
- [x] Informationsbeschaffung
- [x] Branchenstruktur
- [x] SWOT
- [x] BCG optional
- [x] Wettbewerbsstrategie
- [x] Management
- [x] Porter Five Forces für Fair-KGV vorbereitet
- [x] eigene Begründung + Quellen als Pflichtprinzip definiert
- [x] ASML-spezifische Analysethemen definiert

## 1.5 Normalisiertes Rohdatenschema
- [x] GuV-Schlüssel
- [x] Bilanz-Schlüssel
- [x] Cashflow-Schlüssel
- [x] Aktienzahl/Marktdaten
- [x] unternehmensspezifische operative Daten
- [x] Estimates-Schema
- [x] Guidance-Schema
- [x] manuelle Aktienfinder-Eingaben
- [x] Provider-Provenienz

Siehe `docs/RAW_DATA_SCHEMA.md`.

## 1.6 Jahresabschlussbereinigung
- [x] reported / adjustment / normalized als Architektur definiert
- [x] Sondereffekt-Kategorien definiert
- [x] Restatement-Policy definiert
- [x] DCF/Fair-KGV müssen verwendete Basis sichtbar machen
- [ ] exakte Buchdetails S. 422/427 bei Bedarf weiter verifizieren

Siehe `docs/NORMALIZATION_POLICY.md`.

## 1.7 Offene Methodikfragen
Bewusst noch nicht festgelegt:
- [ ] ROE-Endbestand vs. Durchschnittskapital nach Buch verifizieren
- [ ] einzelne ROA-/ROCE-Definitionen final verifizieren
- [ ] 360 vs. 365 Tage nach Buch/Projektpolicy festlegen
- [ ] Owner-Earnings-Details final verifizieren
- [ ] Risiko-KGV vs. vollständiges Fair-KGV
- [ ] Risiko-Dropdown-Punkt-/Prozentwerte
- [ ] exakte Fair-KGV-Scoring-Skalen
- [ ] FCFF/EV-FCF-Definition

Siehe `docs/METHODOLOGY_OPEN_QUESTIONS.md`. Codex darf diese Punkte nicht eigenmächtig entscheiden.

**Phase-1-Entscheidung:** Die Spezifikation ist ausreichend stabil, um die Datenpipeline zu bauen. Offene Buchfragen bleiben blockierend für die jeweilige spätere Formel, nicht für den Raw-Data-Import.

---

# Phase 2 — Datenversorgung 🟡

## 2.1 EODHD Fundamentals v1.1
- [x] Provider-Adapter vorhanden
- [x] v1.1 Fundamentals Endpoint
- [x] maschinenlesbares `eodhd.yaml`-Feldmapping
- [x] GuV-Normalisierung
- [x] Bilanz-Normalisierung
- [x] Cashflow-Normalisierung
- [x] Originalwert + normalisierter Wert/Sign-Policy auditierbar
- [x] Cross-Check-only-Felder markierbar
- [x] Annual Estimates Parser Low/Avg/High/Analyst Count, soweit geliefert
- [x] Tests ohne Live-Netzwerk/API-Key
- [x] Snapshot-Service zum Import in Draft/In-Progress-Analyse
- [x] Refresh einer completed Analyse blockiert
- [x] Streamlit-Seite `Datenimport`
- [ ] **lokal mit echtem `EODHD_API_KEY` ASML.AS testen**
- [ ] tatsächlichen ASML-Payload gegen Mapping prüfen
- [ ] 10-Jahres-Historie validieren
- [ ] Provider-Missing-Fields protokollieren

## 2.2 ASML Primärquellenvalidierung
- [x] offizielle Quellenhierarchie definiert
- [x] konkretes ASML-Feldmapping dokumentiert
- [x] 2025 Kontrollwerte für ersten Importtest dokumentiert
- [x] offizielle US-GAAP-/IFRS-Financial-Statements-Excel als Validierungsquelle identifiziert
- [ ] EODHD 2025 gegen offizielle ASML Financial Statements vergleichen
- [ ] Stichproben älterer Jahre
- [ ] semantische Providerabweichungen dokumentieren

Siehe `docs/ASML_DATA_MAPPING.md`.

## 2.3 Analystenschätzungen
- [x] Datenmodell Low/Average/High/Analyst Count
- [x] Management Guidance getrennt
- [x] EODHD Trend Parser vorbereitet
- [ ] echten ASML Trend Payload prüfen
- [ ] Revisionsfelder prüfen
- [ ] zweite Estimates-Quelle nur bei echtem Bedarf evaluieren

## 2.4 Management Guidance
- [x] strukturiertes Guidance-Datenmodell
- [x] zentrale manuelle Eingabeseite
- [x] Low / Point / High
- [x] Publication Date / URL / Kommentar
- [x] ASML 2026/2030 als Referenzfälle dokumentiert
- [ ] später optional automatisierter Import aus offiziellen IR-Dokumenten

## 2.5 Aktienfinder manuell
- [x] zentrale manuelle Eingabe statt verteilter Excel-Zellen
- [x] Wert / Periode / Quelle / Eingabedatum / Kommentar
- [x] expliziter API-Override möglich und sichtbar speicherbar
- [x] completed Snapshot geschützt
- [ ] komfortablere vordefinierte Eingabeformulare, sobald endgültig klar ist, welche Felder fehlen

## 2.6 Risikofreier EUR-Zins
- [x] ECB-Serie festgelegt: Euro Area AAA 10Y Spot Rate
- [x] ECB Data API Provider implementiert
- [x] CSV-Parser getestet
- [x] interner Wert als Dezimalrate, Originalwert in % p.a. auditierbar
- [x] Snapshot-Speicherung
- [x] Streamlit-Abrufbutton
- [ ] manueller Override später gemeinsam mit Risikomodell

## 2.7 Datenmodell / Provenienz
- [x] Provider field
- [x] Provider original value
- [x] filing date
- [x] restated flag
- [x] cross-check-only
- [x] FinancialAdjustmentSnapshot
- [x] MetricSnapshot
- [x] OperatingFactSnapshot
- [x] InvestmentThesis-Modell
- [ ] Migrationspfad für bestehende lokale Entwicklungsdatenbank

**Definition of Done Phase 2:** erst erfüllt, wenn echter ASML/EODHD-Liveimport und Primärquellenvalidierung durchgeführt wurden.

---

# Phase 3 — Kennzahlenengine

**Erst nach Phase-2-ASML-Validierung beginnen.**

## 3.1 Ertrag und Rentabilität
- [ ] Eigenkapitalrendite (ROE)
- [ ] Umsatzrendite
- [ ] EBIT-/EBITDA-Marge
- [ ] Kapitalumschlag
- [ ] Gesamtkapitalrendite
- [ ] ROCE
- [ ] Umsatzverdienstrate

## 3.2 Finanzielle Stabilität
- [ ] Eigenkapitalquote
- [ ] Gearing
- [ ] Dynamischer Verschuldungsgrad
- [ ] Net Debt/EBITDA
- [ ] Sachinvestitionsquote
- [ ] Anlagenabnutzungsgrad
- [ ] Wachstumsquote
- [ ] Cash-Burn-Rate nur bei Anwendbarkeit
- [ ] Umlauf-/Anlagenintensität
- [ ] Anlagendeckungsgrad I/II
- [ ] Goodwill-Anteil
- [ ] Excel-Erweiterungen gemäß `metrics.yaml`

## 3.3 Working Capital
- [ ] DSO
- [ ] DPO
- [ ] Cash/Quick/Current Ratio
- [ ] Vorratsintensität
- [ ] Inventory Turnover
- [ ] DIO
- [ ] Cash Conversion Cycle
- [ ] Auftragseingang/-bestand bei Anwendbarkeit

## 3.4 Ausschüttung/Kapitalallokation
- [ ] Dividendenquoten
- [ ] Buybacks
- [ ] Netto-Aktienzahlentwicklung
- [ ] Kapitalallokationsanalyse

**DoD:** Jede Kennzahl ist aus nachvollziehbaren Raw Facts reproduzierbar, getestet und gegen ASML plausibilisiert.

---

# Phase 4 — Geführte Geschäftsmodellanalyse

- [ ] UI aus `qualitative.yaml`
- [ ] Antworten / Ratings / Quellen
- [ ] `nicht anwendbar`
- [ ] übernommene Revisionen mit `needs_review`
- [ ] Porter Five Forces
- [ ] SWOT
- [ ] Management
- [ ] Veränderungsvergleich

---

# Phase 5 — Bewertungskennzahlen

## Equitymultiples
- [ ] KGV
- [ ] KBV
- [ ] KCV
- [ ] KUV

## Enterprise Value
- [ ] saubere EV-Brücke
- [ ] EV/EBITDA
- [ ] EV/EBIT
- [ ] EV/FCF/FCFF nach finaler Policy
- [ ] EV/Sales

## Darstellung
- [ ] aktuell
- [ ] 5-Jahres-Median
- [ ] 10-Jahres-Median
- [ ] historische Bandbreite / Perzentile
- [ ] Charts

---

# Phase 6 — Multiplikatorenmethode / Faires KGV

- [ ] Sockel-KGV
- [ ] Finanzielle Stabilität
- [ ] Marktposition / Porter
- [ ] Rentabilitätsmultiplikator
- [ ] Wachstum
- [ ] Individualität
- [ ] Fair-KGV-Formel exakt validieren
- [ ] normalisierte Gewinnbasis
- [ ] fairer Preis je Aktie
- [ ] separates Risiko-KGV für DCF fachlich entscheiden

---

# Phase 7 — Equity-DCF V1: Excel reproduzieren

1. Owner Earnings
2. Diskontierungsfaktor
3. Ewige Rente
4. Fairer Aktienkurs

- [ ] Excel-Owner-Earnings exakt reproduzieren
- [ ] D&A
- [ ] CAPEX
- [ ] Delta Working Capital
- [ ] Eigenkapitalkosten nach validierter Schmidlin-Logik
- [ ] Terminal Value
- [ ] Fair Value je Aktie
- [ ] Margin of Safety separat
- [ ] ASML Kontrollrechnung
- [ ] Unit Tests

---

# Phase 8 — Equity-DCF V2: realistische Prognoseengine

## Prognosephasen
- [ ] Jahr 1: Guidance + Konsens
- [ ] Jahre 2–3: Analyst Low/Base/High
- [ ] Jahre 4–5: eigene fundamentale Annahmen
- [ ] Jahre 6–10: Fade / Mean Reversion
- [ ] Jahr 11+: Terminalphase

## Treiber
- [ ] Umsatz
- [ ] operative Marge
- [ ] Steuerquote
- [ ] CAPEX/Umsatz
- [ ] D&A
- [ ] Working Capital/Umsatz
- [ ] Aktienzahl/Buybacks
- [ ] Terminal Growth

## Konsistenz
- [ ] Wachstum ↔ Reinvestition
- [ ] Margen-Fade
- [ ] CAPEX/D&A langfristig plausibel
- [ ] Terminal-Value-Anteil sichtbar
- [ ] Plausibilitätswarnungen

---

# Phase 9 — Risiko- und Diskontierungsmodell

- [x] ECB-10Y-AAA-Datenquelle vorbereitet
- [ ] Dropdown: Sehr gering / Gering / Mittel / Hoch / Sehr hoch / Benutzerdefiniert
- [ ] Risiko-KGV
- [ ] impliziter Risikoaufschlag
- [ ] resultierende Eigenkapitalkosten
- [ ] Stufenwerte nach Buchvalidierung
- [ ] optionaler Auto-Vorschlag aus qualitativer Analyse
- [ ] manuelles Override
- [ ] CAPM/WACC als Cross-Check
- [ ] Doppelzählung von Wachstum verhindern

---

# Phase 10 — Szenarioengine

- [ ] Worst / Base / Best als zusammenhängende wirtschaftliche Szenarien
- [ ] Analyst Low/Avg/High als kurzfristige Anker
- [ ] Guidance-Korridor
- [ ] Sensitivität Diskontsatz × Terminal Growth
- [ ] Sensitivität Wachstum × Zielmarge
- [ ] später Monte Carlo / Latin Hypercube
- [ ] Korrelationen / Plausibilitätsregeln
- [ ] P10/P25/P50/P75/P90

---

# Phase 11 — Entity-DCF / APV / Spezialfälle

- [ ] FCFF
- [ ] WACC
- [ ] Entity-DCF
- [ ] Equity-vs-Entity Cross-Check
- [ ] APV optional
- [ ] Banken/Versicherungen Sonderlogik
- [ ] Verlustunternehmen / Liquidation
- [ ] Zykliker / normalisierte Gewinne

---

# Phase 12 — Streamlit UX Ausbau

Grundnavigation existiert bereits. Ausbau:

- [ ] Kapitel-Navigation entlang Buch/Excel
- [ ] `ⓘ` überall aus zentralen YAML-Katalogen
- [ ] Historiencharts
- [ ] übersichtliche Datenquellenanzeige
- [ ] komfortables Aktienfinder-Formular
- [ ] Szenarioeditor
- [ ] Investmentthese/Risiken
- [ ] Änderungsansicht zwischen Revisionen visuell ausbauen
- [ ] responsive Darstellung

---

# Phase 13 — PDF-Reporting

## Kurzreport
- [ ] Executive Summary
- [ ] Kernkennzahlen
- [ ] Fair Value / DCF / Multiples
- [ ] Investmentthese / Risiken

## Vollreport
- [ ] Stammdaten und Datenstand
- [ ] Finanzhistorie
- [ ] Kennzahlenkapitel
- [ ] Geschäftsmodell
- [ ] Ausschüttungspolitik
- [ ] Bewertungskennzahlen
- [ ] Fair-KGV
- [ ] DCF
- [ ] Szenarien / Sensitivität
- [ ] Margin of Safety
- [ ] Quellen / Methodik

## Reproduzierbarkeit
- [x] technischer PDF-Snapshot-Prototyp
- [x] alter Snapshot mischt keine Live-Daten ein
- [x] Dateiname mit Unternehmen/Stichtag/Revision
- [ ] professionelles finales Layout

---

# Phase 14 — Qualität / Release

- [ ] zentrale Formeln vollständig testen
- [ ] Datenvalidierung / Missing-Data-UX
- [ ] Logging
- [ ] Datenbankmigrationen
- [ ] Backup / Restore
- [ ] Snapshot Import / Export
- [ ] lokale Windows-Installationsanleitung
- [ ] stabiler erster Release
