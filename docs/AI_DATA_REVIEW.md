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
5. ChatGPT recherchiert per Websuche gegen offizielle Primärquellen und erzeugt die im Paket spezifizierte JSON-Ergebnisdatei.
6. Diese JSON-Datei wird zurück in das lokale Tool geladen.
7. Das Tool validiert Package-ID, Ticker, Stichtag, Revision, Fact-IDs und Schema-Version.
8. Ergebnisse werden lokal als `AIReviewRun` und `AIReviewFinding` gespeichert.
9. PASS wird standardmäßig ausgeblendet; WARN/FAIL/UNKLAR werden sichtbar gemacht.
10. Nur sichere WARN/FAIL-Vorschläge mit offiziellem Wert und Quellen-URL können übernommen werden.
11. `Übernehmen` erzeugt einen `manual_override`; Providerdaten bleiben unverändert erhalten.
12. `Verwerfen` ändert keinen Finanzwert und dokumentiert nur die Entscheidung.
13. Die Preferred-Data-Schicht entscheidet anschließend separat, welche Werte für Kennzahlen freigegeben sind.

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
- **verbindliche interne Felddefinitionen** für semantisch kritische Rohdaten,
- exaktes JSON-Ausgabeformat,
- erwarteten Dateinamen für das Ergebnis.

Die Package-ID ist ein SHA-256-Hash des geprüften Snapshot-Pakets. Wird nach dem Export ein
Finanzwert verändert oder eine andere Revision ausgewählt, wird ein altes Prüfergebnis beim Import
abgelehnt. Verbesserungen am erklärenden Prompt verändern die Package-ID nicht, solange der
zugrunde liegende Snapshot unverändert bleibt.

## Verbindliche Feldsemantik

Die Prüfung vergleicht nicht nur Zahlen, sondern den **wirtschaftlichen Sachverhalt**. Aktuell explizit definiert:

- `ppe_net`: reine Netto-Sachanlagen; separat ausgewiesene Operating-Lease-Right-of-Use-Assets werden ausgeschlossen.
- `short_term_debt`: zinstragende Schulden mit Fälligkeit innerhalb von zwölf Monaten einschließlich Current Portion of Long-Term Debt; Lieferanten- und Leasingverbindlichkeiten bleiben getrennt.
- `depreciation_amortization`: reine Abschreibungen + Amortisation; zusätzliche unspezifische `and other`-Positionen werden nicht automatisch akzeptiert.
- `ebitda`: abgeleitete Kennzahl; Provider-EBITDA ist nur Cross-Check und wird nicht direkt als Berechnungsinput freigegeben.

Diese Definitionen liegen zentral in `src/stock_valuation/data/preferred_data.py` und werden in neue Prüfpakete eingebettet.

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

## Preferred Data nach dem Review

`PASS` bedeutet nicht, dass die Alpha-Vantage-Zahl umgespeichert wird. Der Providerwert bleibt unverändert im Snapshot, erhält aber den Status `reviewed_pass` und darf dadurch als Preferred Data in Downstream-Berechnungen eingehen.

Bei `FAIL`/`WARN` wird der Providerwert erst dann ersetzt, wenn der Nutzer den Korrekturvorschlag **übernimmt**. Dadurch entsteht ein separater `manual_override`, der bei der Source Resolution gewinnt. Ein verworfener Korrekturvorschlag bestätigt den ursprünglichen Providerwert nicht automatisch.

`UNKLAR` bleibt für Berechnungen gesperrt, bis die Felddefinition oder Quellenlage geklärt ist.

## Microsoft-Referenzlauf 2024–2026

Der erste reale Microsoft-Dateiprüflauf zeigte den Nutzen der Trennung:

- 92 Fakten geprüft,
- 81 PASS,
- 2 klare FAIL-Mappingfehler bei `ppe_net` (Providerwert enthielt zusätzlich Operating-Lease-ROU-Assets),
- 9 UNKLAR bei `short_term_debt`, `depreciation_amortization` und `ebitda` aufgrund damaliger Definitions-/Mappingfragen.

Die daraus abgeleiteten Felddefinitionen werden nun in zukünftige Prüfpakete eingebaut. Dadurch soll z. B. `short_term_debt` künftig eindeutig nach der internen Definition geprüft werden können.

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
