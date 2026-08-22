# KI-gestützte Finanzdatenprüfung

## Zweck

Die KI-Prüfung ist eine zusätzliche Qualitätsschicht nach dem automatischen Fundamentals-Import.
Sie soll Providerfehler, semantisch falsche Feldzuordnungen, Einheiten-/Periodenprobleme und
Abweichungen zu offiziellen Abschlüssen sichtbar machen.

Sie ist **kein autonomer Dateneditor** und verwendet im normalen Workflow **keine separat
abgerechnete OpenAI API**.

## Standard-Workflow

1. Alpha Vantage importiert GuV, Bilanz und Cashflow in den Analyse-Snapshot.
2. Deterministische Checks prüfen interne Rechenbeziehungen ohne Netzwerkzugriff.
3. Auf `Finanzdaten` wird ein ChatGPT-Prüfpaket als Markdown-Datei erzeugt.
4. Der Nutzer lädt dieses Prüfpaket in seinem normalen ChatGPT hoch.
5. ChatGPT recherchiert per Websuche gegen offizielle Primärquellen und erzeugt die im Paket
   spezifizierte JSON-Ergebnisdatei.
6. Diese JSON-Datei wird zurück in das lokale Tool geladen.
7. Das Tool validiert Package-ID, Ticker, Stichtag, Revision, Fact-IDs und Schema-Version.
8. Ergebnisse werden lokal als `AIReviewRun` und `AIReviewFinding` gespeichert.
9. PASS wird standardmäßig ausgeblendet; WARN/FAIL/UNKLAR werden sichtbar gemacht.
10. Nur sichere WARN/FAIL-Vorschläge mit offiziellem Wert und Quellen-URL können übernommen werden.
11. `Übernehmen` erzeugt einen `manual_override`; Providerdaten bleiben unverändert erhalten.
12. `Verwerfen` ändert keinen Finanzwert und dokumentiert nur die Entscheidung.

## Warum Datei-Austausch statt direkter API

- keine zusätzliche OpenAI-API-Abrechnung im normalen Workflow,
- Nutzung des bestehenden ChatGPT-Produkts mit Dateiupload und Websuche,
- Nutzer sieht die Recherche und kann bei Bedarf nachfragen,
- Ergebnis bleibt trotzdem maschinenlesbar und reproduzierbar importierbar,
- keine API-Schlüssel oder KI-Modellkonfiguration für die Prüfung erforderlich.

## Prüfpaket

Das Tool erzeugt eine Datei nach dem Muster:

```text
MSFT_2026-08-22_R1_chatgpt_review_package.md
```

Sie enthält:

- Unternehmensidentität,
- Analyse-Stichtag und Revision,
- kryptografische Package-ID,
- ausgewählte bevorzugte Finanzfakten,
- Provider-Feldnamen und Quellenmetadaten,
- lokale Plausibilitätschecks,
- Quellenhierarchie und Prüfregeln,
- exaktes JSON-Ausgabeformat,
- erwarteten Dateinamen für das Ergebnis.

Die Package-ID ist ein SHA-256-Hash des geprüften Snapshot-Pakets. Wird nach dem Export ein
Finanzwert verändert oder eine andere Revision ausgewählt, wird ein altes Prüfergebnis beim Import
abgelehnt.

## Ergebnisdatei

Beispiel:

```json
{
  "schema_version": "1.0",
  "package_id": "...",
  "years_requested": 3,
  "company": {
    "name": "Microsoft Corporation",
    "ticker": "MSFT",
    "analysis_as_of_date": "2026-08-22",
    "revision": 1
  },
  "summary": "...",
  "findings": [
    {
      "fact_id": 123,
      "official_value": 281724000000,
      "status": "PASS",
      "official_label": "Revenue",
      "source_title": "Annual Report 2026",
      "source_url": "https://...",
      "reason": "..."
    }
  ]
}
```

## Quellenhierarchie im Prüfpaket

1. Annual Report / 10-K / 20-F / regulatorisches Filing
2. offizielle Investor-Relations-Finanzstatements
3. Sekundärquellen nur zur Orientierung, niemals allein zur Korrektur

## Statusregeln

- `PASS`: gleicher wirtschaftlicher Sachverhalt und <= 0,5 % Abweichung
- `WARN`: gleicher Sachverhalt und > 0,5 % bis <= 2 % oder geringe nachvollziehbare Darstellungsfrage
- `FAIL`: > 2 % Abweichung oder klare semantische Fehlzuordnung
- `UNKLAR`: keine ausreichend belastbare Primärquelle / Definition nicht sicher vergleichbar

Die Prozentgrenzen sind ein Review-UI-Gate, keine Bewertungsmethodik.

## Persistenz / Audit Trail

### ai_review_runs

Speichert Anzahl geprüfter Jahre, Package-ID, Summary und Zeitstempel. `model` wird beim
Datei-Workflow als `chatgpt_file_review` gekennzeichnet.

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

## Grenzen

- ChatGPT kann eine falsche Quelle auswählen oder eine Abschlusszeile semantisch falsch zuordnen.
- Quellen-URLs und Begründung müssen vor einer wichtigen Korrektur vom Nutzer geprüft werden.
- Quartals- und Jahresperioden dürfen nicht vermischt werden.
- Unterschiedliche Rechnungslegungsstandards oder Restatements können legitime Abweichungen erzeugen.
- Die KI darf niemals eigenständig Providerdaten löschen oder überschreiben.
- Ein importiertes JSON-Ergebnis ist ein Prüfvorschlag, keine automatische Wahrheit.
