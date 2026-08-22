# AGENTS.md

Diese Datei ist die verbindliche Arbeitsanweisung für Codex/Copilot und andere Coding Agents in diesem Repository.

## 1. Projektziel

Wir bauen ein lokales, geführtes Aktienanalyse- und Unternehmensbewertungstool in Python/Streamlit. Die fachliche Reihenfolge orientiert sich am bestehenden Excel-Modell des Nutzers und an Nicolas Schmidlin, **Unternehmensbewertung & Kennzahlenanalyse** (ISBN-13 978-3800645640). Referenzunternehmen während der Entwicklung ist **ASML Holding N.V.** (`ASML.AS`).

Die Anwendung soll die Analyse unterstützen, nicht ersetzen. Sie muss den Nutzer zwingen, Daten, Geschäftsmodell, Marktposition, Management, Risiken und Bewertungsannahmen nachvollziehbar zu dokumentieren.

## 2. Vor jeder Implementierung lesen

1. `AGENTS.md`
2. `CURRENT_TASK.md`
3. `ROADMAP.md`
4. `docs/ARCHITECTURE.md`
5. für fachliche Arbeiten zusätzlich die passende Datei unter `docs/`
6. bei Bewertungslogik immer `docs/DCF_METHOD.md`, `docs/DECISIONS.md` und `docs/METHODOLOGY_OPEN_QUESTIONS.md`

`CURRENT_TASK.md` ist der operative Auftrag. Nicht ungefragt einen späteren Roadmap-Block beginnen.

Nicht eigenmächtig Bewertungsmethodik verändern. Methodische Änderungen zuerst dokumentieren und bei fachlich offenen Fragen die Entscheidung des Nutzers einholen.

## 3. Fachliche Grundregeln

- Historische Rohdaten, manuelle Eingaben, Analystenschätzungen, qualitative Einschätzungen und berechnete Kennzahlen strikt trennen.
- Kennzahlen möglichst aus Rohdaten selbst berechnen, nicht als fertige Providerkennzahl übernehmen.
- Jede externe Zahl braucht Quelle, Zeitraum/Stichtag, Währung, Einheit, Provider und Abrufdatum.
- Manuelle Aktienfinder-Werte sind erlaubt, müssen aber eindeutig als manuell gekennzeichnet werden.
- Abgeschlossene Analysen sind Snapshots. Alte Analysen niemals mit aktuellen Daten überschreiben.
- Eine Aktualisierung erzeugt eine neue Revision/Snapshot.
- DCF-Hauptverfahren ist zunächst das Equity-Verfahren über Owner Earnings.
- Entity-DCF/APV kommen später als Cross-Check/Spezialverfahren.
- Fair Value und Margin of Safety strikt trennen.
- Terminal-Value-Anteil immer anzeigen.
- Wachstum, Marge, CAPEX, Working Capital und Diskontierung müssen ökonomisch zusammenpassen.
- Wachstum darf nicht doppelt positiv wirken, z. B. gleichzeitig höhere Cashflows und künstlich geringerer Risikoaufschlag.
- Analystenschätzungen primär für die ersten 1–3 Prognosejahre verwenden; langfristig eigene fundamentale Annahmen und Fade/Mean Reversion.
- Management-Guidance getrennt vom Analystenkonsens speichern.

## 4. UI-Regeln

- Sprache: Deutsch.
- Kapitelreihenfolge möglichst buch-/excelnah.
- Überschriften z. B. `Eigenkapitalrendite (Return on Equity, ROE)`.
- Jede Kennzahl und jedes qualitative Kriterium besitzt ein `ⓘ` mit eigener, nicht aus dem Buch kopierter Erklärung:
  - Definition
  - Formel
  - Bedeutung
  - Interpretation
  - typische Fallstricke
  - Zusammenhang mit anderen Kennzahlen
  - Kindle-Seite, sofern verifiziert
  - Datenquelle
- Historie standardmäßig 10 Jahre, zusätzlich 5-Jahres-Mittel/Median wenn sinnvoll.
- Datenquelle und Datenstand sichtbar machen.
- Nutzerbegründungen bei qualitativen Einschätzungen speichern.

## 5. Analyse-Lifecycle

Eine Analyse besitzt mindestens:
- Unternehmen
- Stichtag
- Revisionsnummer
- Status: `draft`, `in_progress`, `completed`, `archived`
- vorherige Revision optional
- eingefrorene Rohdaten
- eingefrorene Estimates/Guidance
- manuelle Inputs
- qualitative Einschätzungen
- Bewertungsannahmen
- Bewertungsergebnisse
- Investmentthese und Risiken

Beim Aktualisieren wird eine neue Revision erzeugt. Die Vergleichsfunktion muss Änderungen zwischen zwei Revisionen nach Kategorien zeigen: Fundamentaldaten, Prognosen, Bewertung, qualitative Einschätzung.

## 6. Datenbank

- V1: SQLite lokal.
- Datenbankdateien stehen in `.gitignore`.
- Datenmodell so kapseln, dass später PostgreSQL möglich ist.
- Keine stillen Datenmigrationen; Schemaänderungen nachvollziehbar halten.

## 7. Datenquellen

Siehe `docs/DATA_SOURCES.md`.

Aktueller V1-Stand:
- ASML Investor Relations / Annual Reports: Primärquelle und Referenz für veröffentlichte historische Zahlen sowie Guidance.
- Alpha Vantage: automatischer V1-Kandidat; **nur feldweise nach Primärquellen-Gate freigegeben**, niemals pauschal vertrauen.
- EODHD: Adapter vorhanden; Fundamentals beim getesteten Free-Key nicht freigeschaltet, daher derzeit nur optionaler späterer Fallback/Cross-Check.
- ECB Data API: EUR-Risikofreizins.
- Aktienfinder.de: manuelle Ergänzungen/Overrides.
- weitere Provider nur hinter Provider-Interfaces.

Für ASML dürfen Downstream-Kennzahlen nur Felder verwenden, die der 2024/2025-Primärquellencheck freigegeben hat. FAIL/MISSING-Felder werden nicht still durch offizielle Kontrollwerte ersetzt.

## 8. Engineering-Regeln

- Python 3.12+.
- Berechnungslogik nie direkt in Streamlit-Widgets verstecken.
- UI, Domain, Datenzugriff und Bewertungslogik trennen.
- Jede zentrale Bewertungsformel mit Unit Tests absichern.
- Keine API-Keys, Cookies, Zugangsdaten oder private Analyse-Daten committen.
- `.env` verwenden; `.env.example` pflegen.
- Typannotationen verwenden.
- Fehlende Daten explizit behandeln; keine stillen Fallbacks.
- Vor Abschluss einer Aufgabe Tests ausführen und relevante Roadmap-Checkboxen aktualisieren.

## 9. Arbeitsweise für Codex lokal

1. `CURRENT_TASK.md` lesen.
2. Die dort referenzierten Dokumente lesen.
3. Implementierungsplan kurz erstellen.
4. Nur den abgegrenzten Task bearbeiten.
5. Tests hinzufügen/aktualisieren.
6. `docs/DECISIONS.md` nur bei methodischen/architektonischen Entscheidungen ändern.
7. Fachlich offene Punkte in `docs/METHODOLOGY_OPEN_QUESTIONS.md` dokumentieren, nicht erfinden.
8. `ROADMAP.md` nur abhaken, wenn die Definition of Done erfüllt ist.
9. `CURRENT_TASK.md` nur dann auf die nächste Aufgabe setzen, wenn der aktuelle Block tatsächlich abgeschlossen ist.
10. Ergebnis mit geänderten Dateien, Tests und offenen Punkten zusammenfassen.

## 10. Copyright / Buch

Keine längeren Textpassagen aus dem Buch übernehmen. Wir verwenden eigene Erklärungen und verifizierte Kapitel-/Kindle-Seitenreferenzen.
