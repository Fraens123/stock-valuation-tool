# Current Task

## Phase 2 – generischer offizieller Quellen-Router und historische Datenqualität

Historische Ist-Daten dürfen nicht von Alpha Vantage als Pflichtquelle abhängen. ASML bleibt ein Referenzfall, aber Such-, Import- und Prüflogik müssen generisch für beliebige Unternehmen funktionieren.

## Aktuell implementiert

### 1. Providerunabhängige Identität

- SEC: Ticker/Name → CIK
- GLEIF: Legal Name → LEI
- Ticker, CIK, LEI und Provider-Symbole bleiben getrennte Identifikatoren.
- Die normale Unternehmenssuche benötigt Alpha Vantage nicht.

### 2. Source Router

Standardreihenfolge:

1. SEC Company Facts
2. ESEF/xBRL-JSON
3. Alpha Vantage nur als expliziter Fallback

Innerhalb der SEC-Quellenfamilie gibt es gezielte Ergänzungsstufen aus dem originalen Filing. Der Router mischt keine unterschiedlichen Rechnungslegungsbasen feldweise zu einem scheinbar einheitlichen Abschluss.

### 3. SEC Company Facts

- kein API-Key, aber lokaler `SEC_USER_AGENT`
- Ticker-/CIK-Verzeichnis und Company Facts werden gecacht
- Standardkonzepte aus `us-gaap` und `ifrs-full`
- alternative Standardkonzepte werden pro Periodenende aufgelöst
- Company Extensions werden nicht automatisch als korrekt angenommen
- `short_term_debt` bleibt semantisch gated

### 4. SEC Original-Filing- und Extension-Fallback

Generischer Ablauf:

```text
Company Facts
  ↓ Lücke im 10-Jahres-Fenster
SEC Submissions
  ↓
Originales 10-K / 20-F / 40-F
  ↓
XBRL-Instanz aus Filing-Archiv
  ├─ erlaubter Standardtag → sec_filing_xbrl automatisch ergänzen
  └─ kein Standardtag
       ↓
     firmeneigene XBRL-Tags + Labels durchsuchen
       ↓
     plausiblen Kandidaten als sec_filing_extension speichern
       ↓
     bis semantischem ChatGPT-PASS blockiert
```

Regeln:
- nur Lücken werden ergänzt; Company Facts gewinnt bei identischem Metric/Period-Paar,
- Filing-, Submissions- und Label-Linkbase-Daten werden lokal gecacht,
- Amendments werden berücksichtigt, dürfen aber den vollständigen ursprünglichen Bericht nicht verdecken,
- ein Extension-Kandidat ist **keine automatische fachliche Freigabe**,
- Extension-Kandidaten speichern Originalkonzept, Label soweit vorhanden, Wert, Periode, Quelle und weitere plausible Alternativen,
- kein fehlender Wert wird als Null erfunden,
- `short_term_debt` darf nicht blind aus einem einzelnen Kandidaten als vollständig angenommen oder aus beliebigen Komponenten automatisch summiert werden.

### 5. ESEF

- LEI über GLEIF
- Filings über `filings.xbrl.org`
- Standardkonzepte aus `ifrs-full`
- dimensionale Facts und Extensions werden nicht still als Konzernwerte übernommen
- konkrete Filing-/Report-URL bleibt als Provenienz erhalten

### 6. Preferred Data

- Source Resolution und Calculation Readiness sind getrennt.
- Reihenfolge innerhalb SEC: `sec_companyfacts` → `sec_filing_xbrl` → `sec_filing_extension`.
- `sec_filing_extension` ist immer bis zu einem exakt passenden semantischen PASS blockiert.
- manuelle Overrides bleiben höchste Korrekturebene.
- bekannte semantisch mehrdeutige Primärquellenfelder bleiben blockiert.

### 7. ChatGPT-Dateiprüfung

Der normale bestehende Prüfpaket-Workflow löst jetzt auch historische Extension-Fälle:

- die ausgewählten 2/3/5 aktuellen Geschäftsjahre werden vollständig geprüft,
- zusätzlich werden offene `sec_filing_extension`-Kandidaten aus dem 10-Jahres-Fenster automatisch angehängt,
- der Nutzer muss dafür nicht 10 komplette Jahre tief prüfen,
- bei Extension-Kandidaten ist `PASS` nur bei exakt gleicher wirtschaftlicher Semantik erlaubt,
- bei zu engem/breitem Kandidaten `FAIL`/`UNKLAR`,
- wenn z. B. `short_term_debt` aus mehreren offiziellen Komponenten besteht, kann ein sicherer Gesamtwert als `FAIL`-Korrektur vorgeschlagen und anschließend als auditiertes Override übernommen werden.

### 8. 10-Jahres-Mapping-Check

`src/stock_valuation/data/history_mapping_audit.py`

Prüft automatisch und ohne Netzwerk:
- 10-Jahres-Abdeckung,
- Original-XBRL-/Providerfeld,
- Tagwechsel,
- Quelle/Quellenfamilie,
- Währung,
- Taxonomie,
- echte mehrere Geschäftsjahresenden.

Status:
- `PASS`: vollständig und technisch stabil bzw. ein Extension-Wechsel wurde semantisch aufgelöst,
- `REVIEW`: vollständig, aber Mappingänderung noch nicht fachlich aufgelöst,
- `GAP`: mindestens ein Jahr hat noch gar keinen brauchbaren Kandidaten/Wert.

`sec_companyfacts`, `sec_filing_xbrl` und `sec_filing_extension` gelten als eine SEC-Quellenfamilie. Ein zusätzlicher Opening-/Restatement-Stichtag erzeugt keinen False Positive, wenn der normale Geschäftsjahresendwert vorhanden ist.

### 9. Kennzahlen-UX

- aktive Kennzahlen synchronisieren sich automatisch aus Preferred Data,
- kein manueller Berechnungsbutton,
- methodisch offene Kennzahlen bleiben eingeklappt,
- Mapping-Auffälligkeiten werden auf derselben Kennzahlen-Seite angezeigt.

### 10. Cache / Entwicklung

- Alpha Vantage, SEC, SEC-Filings, GLEIF und ESEF verwenden lokale Caches unter `data/cache/`,
- Cache ist gitignored,
- Offline-Replay bleibt nur im Code/Test und ist aus der normalen UI entfernt,
- alte und neue Prüfpaket-Überschriften bleiben im Offline-Replay kompatibel.

## Neue/angepasste Tests in diesem Block

- `tests/test_sec_filing_provider.py`
- `tests/test_source_router_sec_filing.py`
- `tests/test_sec_filing_preferred_data.py`
- `tests/test_history_mapping_fiscal_year_end.py`
- `tests/test_sec_extension_provider.py`
  - Company-Extension-Kandidaten für Dividend/OCF/Short-Term-Debt
  - offensichtlich falsches Dividendenkonzept (`declared`) wird verworfen
  - Label-Linkbase-Parsing
- `tests/test_source_router_sec_extension.py`
  - Extension-Kandidat wird gespeichert, aber Preferred Data blockiert ihn vor Review
- `tests/test_ai_review_extension_candidate.py`
  - alter Extension-Kandidat wird automatisch an ein kurzes aktuelles Review-Paket angehängt
  - passender PASS macht ihn calculation-ready
- `tests/test_history_mapping_extension_review.py`
  - Extension-Tagwechsel ist vor Review `REVIEW`, nach passendem PASS `PASS`
- bestehende Router-/SEC-/History-/Preferred-Data-/Offline-Replay-Tests bleiben bestehen.

**Wichtig:** Dieser Stand darf erst nach lokalem `pytest -q` als grün bezeichnet werden.

## Nächster Live-Abnahmetest

1. `git pull`
2. `pytest -q`
3. `streamlit run app.py`
4. ASML R1 → `Finanzdaten` → `Finanzdaten laden / aktualisieren`
5. Im Quellen-Router prüfen:
   - `SEC Company Facts`
   - `SEC Original-Filing`
   - `SEC Extension-Mapping`
   - Anzahl gefundener Kandidaten / weiterhin offener Fälle
6. Normales ChatGPT-Prüfpaket mit 3 Jahren herunterladen. Ältere Extension-Kandidaten werden automatisch ergänzt.
7. Prüfpaket in ChatGPT prüfen lassen und JSON wieder importieren.
8. `Kennzahlen` → 10-Jahres-Mapping prüfen. Ziel ist: alle automatisch oder semantisch lösbaren Fälle schließen; echte nicht belegbare Werte bleiben sichtbar offen statt erfunden zu werden.
9. Danach dieselbe Architektur an mindestens einem weiteren SEC-Unternehmen und anschließend einem ESEF-Unternehmen testen.

## Bewusst offene Grenzen

- SEC + ESEF sind keine vollständige Weltabdeckung.
- Ein Company-Extension-Kandidat kann trotz gutem Namen wirtschaftlich falsch/zu eng/zu breit sein; deshalb bleibt der Review zwingend.
- Wenn weder Standard-XBRL noch ein ausreichend plausibler Extension-Kandidat existiert, bleibt der Wert offen und benötigt offiziellen Text-/Tabellenbeleg oder manuellen Override.
- Analystenschätzungen benötigen weiterhin separaten Provider oder manuelle Daten.
- Aktienkurs/Marktdaten bleiben eine getrennte Aufgabe.

## Noch offene Kapitel-2-Methodik

Keine Formeln eigenmächtig festlegen:
- ROE — Kindle S. 94
- Umsatzrendite — Kindle S. 101
- Kapitalumschlag — Kindle S. 107
- Gesamtkapitalrendite — Kindle S. 109
- ROCE — Kindle S. 111
- Umsatzverdienstrate — Kindle S. 114
