# Roadmap

Diese Roadmap ist die verbindliche Entwicklungsreihenfolge. Codex soll immer nur klar abgegrenzte Blöcke daraus bearbeiten.

## Phase 0 — Application Foundation ✅

### 0.1 Projektgrundlage
- [x] Repository anlegen
- [x] `AGENTS.md` anlegen
- [x] Gesamt-Roadmap definieren
- [x] Python-Projektstruktur anlegen
- [x] `.gitignore`, `.env.example`, `pyproject.toml`
- [x] Basistests / Ruff-Konfiguration

### 0.2 Unternehmen
- [x] Company-Domainmodell
- [x] Felder: Name, Ticker, ISIN, Börse, Land, Währung, Sektor, Provider-Symbol
- [x] Unternehmenssuche als Provider-Interface vorbereiten
- [x] lokale Phase-0-Suche implementieren
- [x] ASML als Referenzunternehmen
- [x] spätere Unterstützung mehrerer Listings in der Provider-Architektur berücksichtigen
- [ ] produktive externe Unternehmenssuche anbinden → **Phase 2**

### 0.3 Analyse-Lifecycle
- [x] Analyse erstellen
- [x] Analyse öffnen
- [x] Status: Draft / In Progress / Completed / Archived im Domainmodell
- [x] Revisionsnummer
- [x] vorherige Revision verknüpfen
- [x] abgeschlossene Revision einfrieren
- [x] neue Revision aus älterer Analyse erzeugen
- [x] qualitative Einschätzungen optional als Ausgangspunkt übernehmen
- [x] Bewertungsannahmen optional als Ausgangspunkt übernehmen
- [x] Markt-/Finanzdaten bewusst **nicht** in neue Revision kopieren
- [ ] aktuelle Markt-/API-Daten neu laden → **Phase 2**

### 0.4 Persistenz
- [x] SQLite V1
- [x] SQLAlchemy Models
- [x] Service Layer
- [x] Datenbankdatei in `.gitignore`
- [x] private Excel-Referenzdateien in `.gitignore`
- [x] Schema so gestalten, dass PostgreSQL später möglich ist

### 0.5 Vergleichssystem
- [x] zwei Analysen eines Unternehmens auswählen
- [x] Fundamentaldaten-Diff vorbereiten/implementieren
- [x] Estimates-/Guidance-Diff
- [x] Bewertungsannahmen-Diff
- [x] qualitative Einschätzungen-Diff
- [x] Fair-Value-/Bewertungsergebnis-Diff
- [x] Änderungen nach Kategorien darstellen

### 0.6 PDF-Snapshot-Prototyp
- [x] PDF aus gewähltem Snapshot erzeugen
- [x] PDF-Download in Streamlit
- [x] Dateiname mit Ticker, Stichtag und Revision
- [x] keine Live-Daten beim erneuten Export alter Analysen
- [ ] vollständiger Kurz-/Vollreport → **Phase 13**

### 0.7 Phase-0-Qualität
- [x] Lifecycle-/Freeze-Tests
- [x] Revisionstest
- [x] Vergleichstest
- [x] Company-Suchtest
- [x] PDF-Test
- [x] manueller Acceptance-Test dokumentiert (`docs/PHASE_0_ACCEPTANCE.md`)

**Definition of Done Phase 0:** ASML kann als Unternehmen angelegt werden; mehrere Analyse-Revisionen können lokal gespeichert, geöffnet, eingefroren, revisioniert, miteinander verglichen und als einfacher reproduzierbarer PDF-Snapshot exportiert werden.

---

## Phase 1 — Fachliche Spezifikation / Excel- und Buch-Mapping

- [ ] bestehendes Excel vollständig von oben nach unten inventarisieren
- [ ] jede Kennzahl mit Excel-Formel und Rohdatenbedarf dokumentieren
- [ ] entscheiden: behalten / ergänzen / Spezialfall / nicht sinnvoll
- [ ] Kindle-Seitenmapping vervollständigen
- [ ] eigene Erklärung je Kennzahl definieren
- [ ] Glossarstruktur finalisieren
- [ ] ASML als Referenzfall für jede Kennzahl festlegen
- [ ] Jahresabschlussbereinigung/Sondereffekte als eigenes Konzept definieren

### Buchstruktur im Tool
- [ ] Kapitel 2 Ertrag und Rentabilität
- [ ] Kapitel 3 Finanzielle Stabilität
- [ ] Kapitel 4 Working Capital
- [ ] Kapitel 5 Geschäftsmodell
- [ ] Kapitel 6 Ausschüttungspolitik
- [ ] Kapitel 7 Bewertungskennzahlen
- [ ] Kapitel 8 Unternehmensbewertung
- [ ] Kapitel 9 Margin of Safety / Investmententscheidung

**Definition of Done Phase 1:** Jede geplante Kennzahl/Bewertungsstufe hat Name, Rohdaten, Formel, Bedeutung, Fallstricke, Datenquelle und verifizierte Buchreferenz soweit verfügbar.

---

## Phase 2 — Datenmodell und Datenprovider

### 2.1 Normalisierte Rohdaten
- [ ] GuV-Schema
- [ ] Bilanz-Schema
- [ ] Cashflow-Schema
- [ ] Shares/Dividenden/Buybacks
- [ ] Annual und Quarterly strikt trennen
- [ ] Currency / Unit / Fiscal Period / Source / Retrieved At

### 2.2 EODHD
- [ ] Fundamentals Provider
- [ ] ASML.AS laden
- [ ] 10 Jahre Historie
- [ ] Caching
- [ ] Fehlerbehandlung / Rate Limits
- [ ] Feldmapping dokumentieren

### 2.3 Primärquellen
- [ ] ASML Annual Reports zur Stichprobenvalidierung
- [ ] ASML Management Guidance separat speichern
- [ ] Sondereffekte dokumentieren

### 2.4 Risikofreier Zins
- [ ] ECB Data API
- [ ] EUR AAA 10Y
- [ ] Abrufdatum speichern
- [ ] manuelles Override

### 2.5 Aktienfinder manuell
- [ ] zentrale Eingabeseite
- [ ] Wert, Geschäftsjahr, Quelle, Eingabedatum, Kommentar
- [ ] Forecast-Werte getrennt von historischen Zahlen
- [ ] Overrides sichtbar markieren

### 2.6 Analystenschätzungen
- [ ] Revenue Low / Average / High
- [ ] EPS Low / Average / High
- [ ] Analyst Count
- [ ] Revisionen, falls Provider verfügbar
- [ ] Management Guidance davon getrennt

**Definition of Done Phase 2:** ASML-Rohdaten, Estimates, Guidance und manuelle Inputs können reproduzierbar in einen Analyse-Snapshot übernommen werden.

---

## Phase 3 — Kennzahlenengine

### 3A Ertrag und Rentabilität
- [ ] Eigenkapitalrendite (ROE)
- [ ] Umsatzrendite
- [ ] EBIT-/EBITDA-Marge
- [ ] Kapitalumschlag
- [ ] Gesamtkapitalrendite
- [ ] ROCE
- [ ] Umsatzverdienstrate

### 3B Finanzielle Stabilität
- [ ] Eigenkapitalquote
- [ ] Gearing
- [ ] Dynamischer Verschuldungsgrad
- [ ] Net Debt/EBITDA
- [ ] Sachinvestitionsquote
- [ ] Anlagenabnutzungsgrad
- [ ] Wachstumsquote
- [ ] Cash-Burn-Rate
- [ ] Umlauf-/Anlagenintensität
- [ ] Anlagendeckungsgrad I/II
- [ ] Goodwill-Anteil
- [ ] weitere Excel-Kennzahlen prüfen

### 3C Working Capital
- [ ] Debitorenlaufzeit
- [ ] Kreditorenlaufzeit
- [ ] Liquidität 1./2./3. Grades
- [ ] Vorratsintensität
- [ ] Lagerumschlag / DIO
- [ ] Geldumschlag / Cash Conversion
- [ ] Auftragseingang/-bestand wo sinnvoll

### 3D Ausschüttung/Kapitalallokation
- [ ] Dividenden
- [ ] Ausschüttungsquote
- [ ] Buybacks
- [ ] Share Count Entwicklung
- [ ] Reinvestment vs Ausschüttung

**Definition of Done Phase 3:** Kennzahlen werden aus Rohdaten reproduzierbar berechnet und gegen ASML-Kontrollwerte validiert.

---

## Phase 4 — Geführte Geschäftsmodellanalyse

- [ ] Kompetenzbereich
- [ ] Charakteristika
- [ ] Rahmenbedingungen
- [ ] Informationsbeschaffung
- [ ] Branchenstrukturanalyse
- [ ] Porter Five Forces
- [ ] SWOT
- [ ] BCG optional
- [ ] Wettbewerbsstrategie
- [ ] Management
- [ ] Kommentar und Quelle pro Bewertung
- [ ] Historisierung der Einschätzung

**Definition of Done Phase 4:** qualitative Einschätzungen sind begründet, quellenbezogen und zwischen Revisionen vergleichbar.

---

## Phase 5 — Bewertungskennzahlen

### Equitymultiplikatoren
- [ ] KGV
- [ ] KBV
- [ ] KCV
- [ ] KUV

### Enterprise Value
- [ ] Enterprise Value
- [ ] EV/EBITDA
- [ ] EV/EBIT
- [ ] EV/FCF
- [ ] EV/Sales

### Darstellung
- [ ] aktuell
- [ ] 5-Jahres-Median
- [ ] 10-Jahres-Median
- [ ] historische Bandbreite/Perzentile
- [ ] Chart
- [ ] Quellen/Definitionen

---

## Phase 6 — Multiplikatorenmethode / Faires KGV

- [ ] Sockel-KGV
- [ ] Finanzielle Stabilität
- [ ] Marktposition
- [ ] Rentabilität
- [ ] Wachstum
- [ ] Individualität
- [ ] Bewertung
- [ ] fairer Preis je Aktie
- [ ] exakte Logik gegen Excel/Buch validieren
- [ ] Sondereffekte / normalisierter Gewinn
- [ ] Risiko-KGV getrennt vom vollständigen Fair-KGV definieren

**Definition of Done Phase 6:** bestehende Schmidlin-/Excel-Fair-KGV-Logik ist nachvollziehbar reproduziert und separat testbar.

---

## Phase 7 — Equity-DCF V1: bestehendes Excel reproduzieren

1. Owner Earnings
2. Diskontierungsfaktor
3. Ewige Rente
4. Fairer Aktienkurs

- [ ] Owner-Earnings-Definition exakt festlegen
- [ ] nicht zahlungswirksame Aufwendungen
- [ ] CAPEX
- [ ] Delta Working Capital
- [ ] Eigenkapitalkosten nach bestehender Logik
- [ ] ewige Rente
- [ ] Fair Value je Aktie
- [ ] Margin of Safety getrennt
- [ ] ASML Kontrollrechnung
- [ ] Unit Tests

---

## Phase 8 — Equity-DCF V2: realistische Prognoseengine

### Prognosephasen
- [ ] Jahr 1: Management Guidance + Konsens
- [ ] Jahre 2–3: Analyst Low/Base/High
- [ ] Jahre 4–5: eigene fundamentale Annahmen
- [ ] Jahre 6–10: Fade / Mean Reversion
- [ ] ab Jahr 11: Terminalphase

### Treiber
- [ ] Umsatz
- [ ] operative Marge
- [ ] Steuersatz
- [ ] CAPEX/Umsatz
- [ ] Abschreibungen
- [ ] Working Capital/Umsatz
- [ ] Share Count / Buybacks
- [ ] Terminal Growth

### Regeln
- [ ] CAPEX und Wachstum ökonomisch koppeln
- [ ] Margen-Fade
- [ ] CAPEX/Depreciation langfristig konsistent
- [ ] Terminal-Value-Anteil sichtbar
- [ ] Warnungen bei extremen Annahmen

---

## Phase 9 — Risiko- und Diskontierungsmodell

- [ ] ECB 10Y AAA risikofreier Zins
- [ ] Dropdown: Sehr gering / Gering / Mittel / Hoch / Sehr hoch / Benutzerdefiniert
- [ ] daneben Risiko-KGV
- [ ] impliziter Risikoaufschlag
- [ ] resultierende Eigenkapitalkosten
- [ ] Stufenwerte erst nach Buchvalidierung fixieren
- [ ] Auto-Vorschlag aus qualitativer Analyse optional
- [ ] manuelles Override
- [ ] Mindest-Eigenkapitalkosten optional
- [ ] CAPM/WACC nur als Cross-Check
- [ ] Doppelzählung von Wachstum verhindern

---

## Phase 10 — Szenarioengine

- [ ] Worst / Base / Best als wirtschaftlich zusammenhängende Szenarien
- [ ] Analyst Low/Avg/High als kurzfristige Startwerte
- [ ] Management Guidance als eigener Korridor
- [ ] Sensitivität `Diskontsatz × Terminalwachstum`
- [ ] Sensitivität `Wachstum × Zielmarge`
- [ ] später Monte Carlo / Latin Hypercube
- [ ] Korrelationen und Plausibilitätsregeln
- [ ] P10/P25/P50/P75/P90
- [ ] Wahrscheinlichkeit über/unter Marktpreis nur als Modelloutput kennzeichnen

---

## Phase 11 — Entity-DCF / APV / Spezialfälle

- [ ] FCFF
- [ ] WACC
- [ ] Entity-DCF
- [ ] Equity-vs-Entity Cross-Check
- [ ] APV optional
- [ ] Banken/Versicherungen Sonderlogik
- [ ] Verlustunternehmen
- [ ] Liquidationsansatz
- [ ] Zykliker / normalisierte Gewinne

---

## Phase 12 — Streamlit UX

- [x] Startseite mit lokaler ASML-Suche als Phase-0-Basis
- [x] Neue Analyse / Analyse öffnen / Vergleich als Phase-0-Basis
- [x] zuletzt bearbeitete Analysen als Phase-0-Basis
- [ ] produktive Unternehmenssuche
- [ ] Kapitel-Navigation
- [ ] `ⓘ` Popover überall
- [ ] Historiencharts
- [ ] manuelle Eingabezentrale
- [ ] Szenarioeditor
- [ ] Investmentthese und Risiken als strukturierte Formulare
- [ ] erweiterte Änderungsansicht zwischen Revisionen
- [ ] Datenquellenanzeige

---

## Phase 13 — PDF-Reporting

### Kurzreport
- [ ] 5–10 Seiten
- [ ] Executive Summary
- [ ] Kernkennzahlen
- [ ] Fair Value / DCF / Multiples
- [ ] Investmentthese und Risiken

### Vollreport
- [ ] Stammdaten / Datenstand
- [ ] Finanzhistorie
- [ ] Kennzahlenkapitel
- [ ] Geschäftsmodell
- [ ] Ausschüttungspolitik
- [ ] Bewertungskennzahlen
- [ ] Faires KGV
- [ ] DCF
- [ ] Szenarien / Sensitivität
- [ ] Investmentthese / Risiken
- [ ] Margin of Safety
- [ ] Quellen / Methodik

### Reproduzierbarkeit
- [x] Report-Grundprinzip: ausschließlich aus gewähltem Analyse-Snapshot
- [x] alte Analyse darf im Prototyp nicht mit heutigen Daten vermischt werden
- [x] PDF-Dateiname enthält Unternehmen/Ticker, Stichtag und Revision
- [ ] vollständige Report-Inhalte

---

## Phase 14 — Qualität / Release

- [ ] Testabdeckung zentrale Formeln
- [ ] Datenvalidierung
- [ ] Fehler-/Missing-Data UX
- [ ] Logging
- [ ] Backup/Restore der SQLite-Datenbank
- [ ] Import/Export Analyse-Snapshot
- [ ] lokale Installationsanleitung Windows
- [ ] erster stabiler Release
