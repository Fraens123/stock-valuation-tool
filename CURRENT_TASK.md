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

Der Router mischt keine unterschiedlichen Rechnungslegungsbasen feldweise zu einem scheinbar einheitlichen Abschluss.

### 3. SEC Company Facts

- kein API-Key, aber lokaler `SEC_USER_AGENT`
- Ticker-/CIK-Verzeichnis und Company Facts werden gecacht
- Standardkonzepte aus `us-gaap` und `ifrs-full`
- alternative Standardkonzepte werden pro Periodenende aufgelöst
- Company Extensions werden nicht automatisch geraten
- `short_term_debt` bleibt semantisch gated

### 4. SEC Original-Filing-Fallback

Siehe `docs/SEC_FILING_FALLBACK.md`.

Neue generische Ergänzung:

```text
Company Facts
  ↓ Lücke im 10-Jahres-Fenster
SEC Submissions
  ↓
Originales 10-K / 20-F / 40-F
  ↓
XBRL-Instanz aus Filing-Archiv
  ↓
Standardtag sicher → sec_filing_xbrl ergänzen
kein Standardtag → offen / Extension- oder Textprüfung erforderlich
```

Regeln:
- nur Lücken werden ergänzt; Company Facts gewinnt bei identischem Metric/Period-Paar,
- Filing- und Submissions-Daten werden lokal gecacht,
- Amendments werden berücksichtigt, dürfen aber den vollständigen ursprünglichen Bericht nicht verdecken,
- keine automatische Extension-Zuordnung,
- kein fehlender Wert wird als Null erfunden,
- `short_term_debt` bleibt auch aus `sec_filing_xbrl` bis zur semantischen Freigabe blockiert.

### 5. ESEF

- LEI über GLEIF
- Filings über `filings.xbrl.org`
- Standardkonzepte aus `ifrs-full`
- dimensionale Facts und Extensions werden nicht still als Konzernwerte übernommen
- konkrete Filing-/Report-URL bleibt als Provenienz erhalten

### 6. Preferred Data

- Source Resolution und Calculation Readiness sind getrennt.
- `sec_filing_xbrl` ist offizielle Primärquelle, aber niedriger priorisiert als `sec_companyfacts`.
- manuelle Overrides bleiben höchste Korrekturebene.
- bekannte semantisch mehrdeutige Primärquellenfelder bleiben blockiert.

### 7. 10-Jahres-Mapping-Check

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
- `PASS`: vollständig und technisch stabil,
- `REVIEW`: vollständig, aber Mappingänderung,
- `GAP`: mindestens ein Jahr fehlt.

`sec_companyfacts` und `sec_filing_xbrl` gelten als eine SEC-Quellenfamilie. Ein zusätzlicher Opening-/Restatement-Stichtag erzeugt keinen False Positive, wenn der normale Geschäftsjahresendwert vorhanden ist.

### 8. Kennzahlen-UX

- aktive Kennzahlen synchronisieren sich automatisch aus Preferred Data,
- kein manueller Berechnungsbutton,
- methodisch offene Kennzahlen bleiben eingeklappt,
- Mapping-Auffälligkeiten werden auf derselben Kennzahlen-Seite angezeigt.

### 9. Cache / Entwicklung

- Alpha Vantage, SEC, SEC-Filings, GLEIF und ESEF verwenden lokale Caches unter `data/cache/`,
- Cache ist gitignored,
- Offline-Replay bleibt nur im Code/Test und ist aus der normalen UI entfernt.

## Neue/angepasste Tests in diesem Block

- `tests/test_sec_filing_provider.py`
  - Standardfakten aus Original-XBRL-Instanz
  - dimensionale und Company-Extension-Fakten werden nicht automatisch übernommen
  - `short_term_debt` bleibt ein roher Standardfakt für das spätere semantische Gate
- `tests/test_source_router_sec_filing.py`
  - Company-Facts-Lücke wird als separate `sec_filing_xbrl`-Primärquelle ergänzt
- `tests/test_sec_filing_preferred_data.py`
  - Company Facts gewinnt bei gleicher Periode
  - Filing-OCF ist calculation-ready
  - Filing-`short_term_debt` bleibt blockiert
- `tests/test_history_mapping_fiscal_year_end.py`
  - Opening Balance im selben Kalenderjahr ist kein zweites FY
  - Company Facts und Filing-Fallback sind eine Quellenfamilie
- bestehende Router-/SEC-/History-/Preferred-Data-Tests bleiben bestehen.

**Wichtig:** Dieser Stand darf erst nach lokalem `pytest -q` als grün bezeichnet werden.

## Nächster Live-Abnahmetest

1. `git pull`
2. `pytest -q`
3. `streamlit run app.py`
4. ASML R1 → `Finanzdaten` → `Finanzdaten laden / aktualisieren`
5. Im Quellen-Router prüfen:
   - `SEC Company Facts`
   - `SEC Original-Filing`
   - Anzahl ergänzter Standardfakten
   - Anzahl offen gebliebener Extension-/Textfälle
6. Danach `Kennzahlen` öffnen und 10-Jahres-Mapping erneut prüfen.
7. Erwartete ASML-Schwerpunkte aus dem bisherigen Audit:
   - `operating_cash_flow` 2016: Filing-Fallback sollte prüfen, ob ein Standardtag ergänzt werden kann,
   - `short_term_debt` 2016/2017: Standardfakt darf ergänzt werden, bleibt aber semantisch gated,
   - `dividends_paid` 2019–2025: wenn nur Company-Extension/Textzeile vorhanden ist, muss die Lücke sichtbar offen bleiben,
   - `shareholders_equity` 2018: Opening-/Restatement-Instant soll keinen falschen Doppel-FY-Hinweis mehr erzeugen.
8. Danach dieselbe Architektur an mindestens einem weiteren SEC-Unternehmen (z. B. Microsoft) und anschließend einem ESEF-Unternehmen testen.

## Bewusst offene Grenzen

- SEC + ESEF sind keine vollständige Weltabdeckung.
- Company Extensions werden noch nicht automatisch semantisch auf interne Felder gemappt.
- Ein gezielter Review-Workflow für verbleibende Filing-Extension-Kandidaten ist der nächste mögliche Datenqualitätsblock, falls der Live-Test solche Lücken bestätigt.
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
