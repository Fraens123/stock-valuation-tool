# SEC Original-Filing-Fallback

## Zweck

SEC Company Facts bleibt der schnelle Hauptimport für SEC-Berichterstatter. Die API aggregiert jedoch nur bestimmte entity-wide Fakten aus Standardtaxonomien. Ein fehlender Company-Facts-Wert bedeutet deshalb nicht automatisch, dass der veröffentlichte Geschäftsbericht keine Zahl enthält.

Der Original-Filing-Fallback ergänzt gezielt Lücken innerhalb derselben SEC-/Rechnungslegungsbasis.

```text
SEC Company Facts
  ↓
10-Jahres-Abdeckung
  ↓ nur bei Lücken
SEC Submissions → Annual Filing (10-K / 20-F / 40-F)
  ↓
SEC Filing Archive / index.json
  ↓
XBRL-Instanz (_htm.xml oder klassische Instance XML)
  ↓
Standardkonzept sicher gefunden? ── ja → sec_filing_xbrl
  │
  └─ nein → offen; Extension-/Textprüfung erforderlich
```

## Identifikation des Filings

- CIK bleibt der Unternehmensschlüssel.
- Filing-Historie: `data.sec.gov/submissions/CIK##########.json`.
- Ältere Submission-Dateien werden nur für relevante Zieljahre nachgeladen.
- Annual Forms: 10-K/10-K/A, 20-F/20-F/A, 40-F/40-F/A.
- Zuordnung erfolgt über `reportDate`, nicht über das Kalenderjahr des Filing-Datums.
- Bei Amendments werden Filings eines Geschäftsjahres vom neuesten zum älteren geprüft. Ein dünnes Amendment darf den ursprünglichen vollständigen Bericht nicht verdecken.

## Filing-Archiv

Der Provider liest das öffentliche SEC-Archiv anhand von CIK und Accession Number. `index.json` dient zur Dateidiscovery. Bevorzugt werden extrahierte XBRL-Instanzen (`*_htm.xml`), bei älteren Filings klassische XBRL-Instance-XML-Dateien.

Alle JSON- und Textantworten werden lokal unter `data/cache/` gecacht.

## Automatisch erlaubte Fakten

Automatisch importiert werden ausschließlich:

- bekannte Standardkonzepte aus dem gemeinsamen `CONCEPT_MAP`,
- Taxonomien `us-gaap` bzw. `ifrs-full`,
- entity-wide Kontexte ohne zusätzliche Segment-/Dimensionsangaben,
- Bilanzwerte am Filing-`reportDate`,
- GuV-/Cashflow-Werte mit jährlichem Duration-Kontext,
- Werte in der erwarteten Berichtswährung.

Der Provider lautet `sec_filing_xbrl`. Das konkrete XBRL-Dokument wird als `source_url` am Fakt gespeichert.

## Extension-Tags

Company-spezifische Extension-Tags werden **nicht automatisch** einem internen Feld zugeordnet. Wenn Company Facts eine Lücke hat und das Originalfiling keinen erlaubten Standard-Tag liefert, bleibt die Feld/Jahr-Kombination offen und wird als `semantic_review_required` gemeldet.

Eine spätere Extension-Prüfung darf einen Kandidaten vorschlagen, aber niemals ohne semantische Freigabe in Preferred Data übernehmen.

## Preferred Data

Priorität bei gleicher Metrik/Periode:

1. bestätigter manueller Override,
2. andere höher priorisierte Primärquelle nach zentraler Source Resolution,
3. `sec_companyfacts`,
4. `sec_filing_xbrl`,
5. Provider-Fallbacks.

Der Filing-Fallback ersetzt Company Facts also nicht, wenn beide denselben Fakt liefern. Er füllt nur Lücken.

`sec_companyfacts` und `sec_filing_xbrl` zählen im 10-Jahres-Mapping als dieselbe **SEC-Quellenfamilie**. Ein Wechsel des Extraktionspfads allein erzeugt keine Quellenwechsel-Warnung. Ein Wechsel des XBRL-Konzepts bleibt dagegen sichtbar.

## Semantische Gates

Primärquelle bedeutet nicht automatisch calculation-ready. Besonders `short_term_debt` bleibt sowohl bei `sec_companyfacts` als auch `sec_filing_xbrl` bis zur semantischen Prüfung blockiert, weil das interne Feld mehrere kurzfristige zinstragende Schuldkomponenten umfassen kann. Komponenten werden nicht blind addiert.

## Geschäftsjahresende / Restatement-Instants

Der 10-Jahres-Mapping-Check bestimmt das normale Geschäftsjahresende aus den gespeicherten FY-Fakten. Zusätzliche Eröffnungs- oder Restatement-Stichtage im selben Kalenderjahr werden nicht als zweites Geschäftsjahr gewertet, wenn der reguläre Jahresendstichtag vorhanden ist.

## Grenzen

- Der Fallback ist ein gezielter Parser für bekannte Standardkonzepte, kein vollständiger XBRL-Prozessor.
- Texttabellen und Company Extensions werden nicht automatisch semantisch interpretiert.
- Fehlende XBRL-Instanzen bleiben sichtbar offen.
- Es wird niemals ein fehlender Wert als Null erfunden.
