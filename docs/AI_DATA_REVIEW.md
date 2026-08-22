# KI-gestützte Finanzdatenprüfung

## Zweck

Die KI-Prüfung ist eine zusätzliche Qualitätsschicht nach dem automatischen Fundamentals-Import.
Sie soll Providerfehler, semantisch falsche Feldzuordnungen, Einheiten-/Periodenprobleme und
Abweichungen zu offiziellen Abschlüssen sichtbar machen.

Sie ist **kein autonomer Dateneditor**.

## Workflow

1. Alpha Vantage importiert GuV, Bilanz und Cashflow in den Analyse-Snapshot.
2. Deterministische Checks prüfen interne Rechenbeziehungen ohne Netzwerkzugriff.
3. `KI-Prüfung starten` sendet die ausgewählten letzten Geschäftsjahre an die OpenAI Responses API.
4. Das Modell erhält das eingebaute Web-Search-Tool und muss offizielle Primärquellen priorisieren.
5. Structured Outputs liefern für jeden eingereichten Snapshot-Fakt genau einen Review-Eintrag.
6. Ergebnisse werden lokal als `AIReviewRun` und `AIReviewFinding` gespeichert.
7. PASS wird standardmäßig ausgeblendet; WARN/FAIL/UNKLAR werden sichtbar gemacht.
8. Nur sichere WARN/FAIL-Vorschläge mit offiziellem Wert und Quellen-URL können übernommen werden.
9. `Übernehmen` erzeugt einen `manual_override`; Providerdaten bleiben unverändert erhalten.
10. `Verwerfen` ändert keinen Finanzwert und dokumentiert nur die Entscheidung.

## Quellenhierarchie im Prompt

1. Annual Report / 10-K / 20-F / regulatorisches Filing
2. offizielle Investor-Relations-Finanzstatements
3. Sekundärquellen nur zur Orientierung, niemals allein zur automatischen Korrektur

## Statusregeln

- `PASS`: gleicher wirtschaftlicher Sachverhalt und <= 0,5 % Abweichung
- `WARN`: gleicher Sachverhalt und > 0,5 % bis <= 2 % oder geringe nachvollziehbare Darstellungsfrage
- `FAIL`: > 2 % Abweichung oder klare semantische Fehlzuordnung
- `UNKLAR`: keine ausreichend belastbare Primärquelle / Definition nicht sicher vergleichbar

Die Prozentgrenzen sind ein Review-UI-Gate, keine Bewertungsmethodik.

## Persistenz / Audit Trail

### ai_review_runs

Speichert Modell, Anzahl geprüfter Jahre, OpenAI Response-ID, Summary und Zeitstempel.

### ai_review_findings

Speichert:
- Periode und Metrik,
- importierten Wert,
- gefundenen offiziellen Wert,
- Abweichung,
- Verdict,
- offizielle Bezeichnung,
- Quellen-URL,
- Begründung,
- Entscheidung (`pending`, `accepted`, `rejected`).

## Datenschutz / API

Lokale Konfiguration:

```text
OPENAI_API_KEY=...
OPENAI_REVIEW_MODEL=gpt-5.4
```

Der API-Key gehört ausschließlich in `.env` und niemals ins Repository.
Die Responses-Anfrage wird mit `store=False` gesendet. Die für den Analyse-Audit benötigten
strukturierten Ergebnisse werden lokal in SQLite gespeichert.

OpenAI-Modell- und Web-Search-Nutzung kann API-Kosten verursachen und ist getrennt von einem
ChatGPT-Abonnement.

## Grenzen

- Ein Modell kann eine falsche Quelle auswählen oder eine Abschlusszeile semantisch falsch zuordnen.
- Quellen-URLs und Begründung müssen vor einer wichtigen Korrektur vom Nutzer geprüft werden.
- Quartals- und Jahresperioden dürfen nicht vermischt werden.
- Unterschiedliche Rechnungslegungsstandards oder Restatements können legitime Abweichungen erzeugen.
- Die KI darf niemals eigenständig Providerdaten löschen oder überschreiben.
