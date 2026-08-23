# SEC Original-Filing-Fallback

## Zweck

SEC Company Facts bleibt der schnelle Hauptimport für SEC-Berichterstatter. Die API aggregiert jedoch nur bestimmte entity-wide Fakten. Ein fehlender Company-Facts-Wert bedeutet deshalb nicht automatisch, dass der veröffentlichte Geschäftsbericht keine Zahl enthält.

Der Original-Filing-Fallback ergänzt gezielt Lücken innerhalb derselben SEC-/Rechnungslegungsbasis. Wenn kein unterstützter Standardtag existiert, kann eine zweite Stufe einen **firmeneigenen XBRL-Kandidaten** entdecken. Dieser Kandidat ist ausdrücklich noch keine fachlich akzeptierte Zuordnung.

```text
SEC Company Facts
  ↓
10-Jahres-Abdeckung
  ↓ nur bei Lücken
SEC Submissions → Annual Filing (10-K / 20-F / 40-F)
  ↓
SEC Filing Archive / index.json
  ↓
XBRL-Instanz
  ├─ Standardkonzept sicher gefunden → sec_filing_xbrl
  └─ kein Standardkonzept
       ↓
     Company-Extension-Tags + Label-Linkbase
       ↓
     plausibler Kandidat → sec_filing_extension
       ↓
     semantischer ChatGPT-Review zwingend
       ├─ PASS → calculation-ready
       ├─ FAIL/WARN + sichere offizielle Zahl → optional bestätigter Override
       └─ UNKLAR → blockiert
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

Für Company-Extensions werden zusätzlich vorhandene Label-Linkbases (`*_lab.xml`) gelesen. Sie liefern menschenlesbare Bezeichnungen für firmeneigene XBRL-Konzepte.

Alle JSON- und Textantworten werden lokal unter `data/cache/` gecacht.

## Stufe 1 – automatisch erlaubte Standardfakten

Automatisch importiert werden ausschließlich:

- bekannte Standardkonzepte aus dem gemeinsamen `CONCEPT_MAP`,
- Taxonomien `us-gaap` bzw. `ifrs-full`,
- entity-wide Kontexte ohne zusätzliche Segment-/Dimensionsangaben,
- Bilanzwerte am Filing-`reportDate`,
- GuV-/Cashflow-Werte mit jährlichem Duration-Kontext,
- Werte in der erwarteten Berichtswährung.

Der Provider lautet `sec_filing_xbrl`. Das konkrete XBRL-Dokument wird als `source_url` am Fakt gespeichert.

## Stufe 2 – Company-Extension-Kandidaten

Wenn Company Facts und die Standard-Filing-Stufe eine Lücke lassen, durchsucht `sec_extension.py` die firmeneigenen XBRL-Konzepte desselben offiziellen Filings.

Die Kandidatensuche verwendet:
- Concept-Name,
- menschenlesbares Label aus der Label-Linkbase, soweit vorhanden,
- Periode und Kontextart,
- Berichtswährung,
- interne Zielmetrik und deren erlaubte Standardkonzepte als sprachliche Vergleichsbasis.

Offensichtlich andere Sachverhalte werden schon vor dem Review ausgeschlossen, z. B. `DividendsDeclared` für tatsächlich gezahlte Dividenden oder Financing/Investing Cash Flow für `operating_cash_flow`.

Ein gefundener Kandidat wird als `sec_filing_extension` gespeichert. Provenienz umfasst mindestens:
- internes Zielfeld,
- Original-Extension-Concept,
- Label, soweit vorhanden,
- Namespace,
- Wert/Währung/Periode,
- Matching-Hinweis,
- konkrete Filing-URL,
- weitere plausible Kandidaten im selben Filing, soweit gefunden.

**Wichtig:** Diese Stufe klassifiziert nur einen Kandidaten für die nachfolgende fachliche Prüfung. Sie behauptet nicht, dass der Extension-Tag semantisch korrekt gemappt ist.

## Preferred Data

Priorität bei gleicher Metrik/Periode:

1. bestätigter manueller Override,
2. andere höher priorisierte Primärquelle nach zentraler Source Resolution,
3. `sec_companyfacts`,
4. `sec_filing_xbrl`,
5. `sec_filing_extension`,
6. Provider-Fallbacks.

`sec_filing_extension` kann damit eine echte Lücke sichtbar mit einem offiziellen Kandidaten füllen, aber die Calculation-Readiness bleibt bis zum semantischen PASS **false**.

`sec_companyfacts`, `sec_filing_xbrl` und `sec_filing_extension` zählen im 10-Jahres-Mapping als dieselbe **SEC-Quellenfamilie**. Ein Wechsel des Extraktionspfads allein ist kein Wechsel der Rechnungslegungsquelle.

## ChatGPT-Dateiprüfung

Die bestehende ChatGPT-Dateiprüfung übernimmt die semantische Freigabe. Der Nutzer muss dafür nicht zehn komplette Jahre tief prüfen:

- die gewählten aktuellen 2/3/5 Geschäftsjahre werden vollständig in das Prüfpaket aufgenommen,
- zusätzlich werden alle `sec_filing_extension`-Kandidaten aus dem aktuellen 10-Jahres-Mappingfenster automatisch angehängt.

Für Extension-Kandidaten gelten strengere Regeln:
- `PASS` nur bei exakt gleicher wirtschaftlicher Bedeutung wie das interne Feld,
- zu enger/zu breiter Kandidat → `FAIL` oder `UNKLAR`,
- wenn eine korrekte offizielle Gesamtzahl eindeutig ermittelbar ist, kann `FAIL` diese als `official_value` zurückgeben; der Nutzer kann sie anschließend als auditierten Override übernehmen.

Besonders bei `short_term_debt` darf ein einzelner Current-Portion- oder Borrowings-Tag nicht automatisch als vollständige kurzfristige Verschuldung gelten. Komponenten werden nicht blind addiert.

## 10-Jahres-Mapping nach Review

Ein Extension-Tagwechsel bleibt zunächst `REVIEW`. Er gilt als fachlich aufgelöst, wenn:
- ein exakt passender Review-Fund `PASS` ist, oder
- eine daraus begründete offizielle Korrektur als manueller Override bestätigt wurde.

Dann kann die 10-Jahres-Serie wieder `PASS` erreichen. Ein Wert, für den weder Standardfakt noch plausibler Extension-Kandidat existiert, bleibt dagegen als echte Lücke sichtbar.

## Geschäftsjahresende / Restatement-Instants

Der 10-Jahres-Mapping-Check bestimmt das normale Geschäftsjahresende aus den gespeicherten FY-Fakten. Zusätzliche Eröffnungs- oder Restatement-Stichtage im selben Kalenderjahr werden nicht als zweites Geschäftsjahr gewertet, wenn der reguläre Jahresendstichtag vorhanden ist.

## Grenzen

- Der Fallback ist ein gezielter Parser, kein vollständiger XBRL-Prozessor.
- Ein guter Concept-Name oder ein gutes Label beweist keine wirtschaftliche Gleichheit; deshalb ist der Review zwingend.
- Texttabellen ohne nutzbaren XBRL-Fakt bleiben offen und benötigen einen offiziellen Text-/Tabellenbeleg oder manuellen Override.
- Fehlende XBRL-Instanzen bleiben sichtbar offen.
- Es wird niemals ein fehlender Wert als Null erfunden.
