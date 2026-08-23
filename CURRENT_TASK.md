# Current Task

## Phase 2 – generischer offizieller Quellen-Router und historische Datenqualität

Historische Ist-Daten dürfen nicht mehr von Alpha Vantage als Pflichtquelle abhängen. ASML bleibt ein Referenzfall, aber die normale Suche/Importlogik muss für beliebige Unternehmen funktionieren.

## Aktuell implementiert

### 1. Providerunabhängige Unternehmensidentität

- `src/stock_valuation/companies/discovery.py`
- `src/stock_valuation/data/providers/sec.py`
- `src/stock_valuation/data/providers/gleif.py`

Normaler Suchweg:

```text
Name/Ticker
  ├─ SEC-Verzeichnis → Ticker + CIK
  └─ GLEIF → Legal Entity + LEI
```

CIK und LEI werden getrennt vom Börsenticker in `CompanyProviderSymbol` gespeichert.

Die Streamlit-Seite `Unternehmen` verwendet für die normale Suche nicht mehr Alpha Vantage.

### 2. Historischer Source Router

- `src/stock_valuation/data/source_router.py`

Standardreihenfolge:

1. SEC Company Facts
2. ESEF/xBRL-JSON
3. Alpha Vantage nur wenn der Nutzer den Fallback ausdrücklich aktiviert

Der Router wählt zunächst eine kohärente historische Quelle und mischt nicht still verschiedene Provider innerhalb einer Abschlussserie.

### 3. SEC

- kein API-Key
- lokal erforderlich: `SEC_USER_AGENT`
- öffentliches Ticker/CIK-Verzeichnis wird gecacht
- Company Facts wird gecacht
- Standardkonzepte aus `us-gaap` und `ifrs-full` werden normalisiert
- Company Extensions werden nicht geraten

Bekannte semantische Sperre:
- `sec_companyfacts + short_term_debt` ist trotz Primärquelle **nicht automatisch calculation-ready**, weil die interne Definition mehrere kurzfristige Schuldenkonzepte umfassen kann.
- Ein passender ChatGPT-Review `PASS` oder bestätigter Override kann das Feld freigeben.

### 4. GLEIF

- kein API-Key
- Name → LEI
- dient nur der Identität, nicht als Finanzdatenquelle
- automatische Auflösung nur bei ausreichend eindeutigem Legal-Name-Match
- Responses werden lokal gecacht

### 5. ESEF

- `src/stock_valuation/data/providers/esef_registry.py`
- LEI → Filings über `filings.xbrl.org`
- xBRL-JSON wird bevorzugt
- nur standardisierte `ifrs-full`-Konzepte werden automatisch gemappt
- jährliche Duration-Facts für GuV/Cashflow
- Instant-Facts für Bilanz
- segmentierte/dimensionale Facts werden nicht still als Konzernsumme verwendet
- konkrete Filing-/Report-URL wird pro Fact gespeichert, soweit vorhanden
- heruntergeladene Registry-/Filingdaten werden lokal gecacht

Der bestehende ESEF-XHTML/ZIP-Parser bleibt als technischer Fallback im Code.

### 6. Finanzdaten-UI

`pages/1_Datenimport.py`:

- Hauptbutton: `Finanzdaten laden / aktualisieren`
- SEC → ESEF → optional Alpha-Fallback
- zeigt Router-Versuche in einem technischen Expander
- historische Daten funktionieren ohne Alpha-Vantage-Key
- Analystenschätzungen sind ein separater optionaler Schritt
- ChatGPT-Prüfung bleibt für semantischen Cross-Check und Provider-Kontrolle

### 7. Preferred Data

- `esef_xbrl_json` ist als Primärquelle integriert
- Source Priority und Calculation Readiness bleiben getrennt
- manuelle Overrides bleiben höchste praktische Korrekturebene
- Primärquellenwerte mit bekannter semantischer Mehrdeutigkeit können blockiert bleiben

### 8. Generischer 10-Jahres-Mapping-Check

- `src/stock_valuation/data/history_mapping_audit.py`
- arbeitet ausschließlich auf dem gespeicherten Snapshot; kein Netzwerk/API-Request
- keine Unternehmens-Sonderlogik
- prüft standardmäßig die letzten 10 Geschäftsjahre je importiertem internem Feld
- prüft:
  - Jahresabdeckung/Lücken
  - Original-XBRL-/Provider-Feld
  - Tagwechsel und Wechseljahr
  - zugrunde liegende Quelle
  - Berichtswährung
  - Taxonomie (`us-gaap`, `ifrs-full` bzw. Provider-Taxonomie)
  - mehrere Geschäftsjahres-Enden innerhalb desselben Kalenderjahres
- Status:
  - `PASS`: 10/10 und technisch unverändertes Mapping
  - `REVIEW`: vollständige Serie, aber Tag-/Quellen-/Währungs-/Taxonomiewechsel oder doppeltes Geschäftsjahresende
  - `GAP`: mindestens ein Jahr fehlt
- Tagwechsel sind ausdrücklich **kein automatischer Fehler**; sie lösen nur fachliche Prüfung aus.
- manuelle Overrides werden für die Mapping-Kontinuität nicht anstelle der zugrunde liegenden Originalquelle verwendet.
- Anzeige ist automatisch auf `Kennzahlen`; kein zusätzlicher Berechnungs-/Prüfbutton.
- stabile Detailzeilen sind standardmäßig eingeklappt, Auffälligkeiten werden automatisch aufgeklappt.

### 9. Kennzahlen-UX

- aktive Kennzahlen werden beim Öffnen der Seite automatisch aus Preferred Data synchronisiert
- kein manueller Button `Aktive Kennzahlen aus Preferred Data berechnen`
- identische Input-Hashes führen zu keinem unnötigen Datenbank-Rewrite
- methodisch noch offene Kennzahlen bleiben eingeklappt
- `primary_reviewed_pass` wird in der Preferred-Data-Zusammenfassung korrekt als geprüfte Primärquelle gezählt

### 10. Cache / Entwicklung

- Alpha-Vantage-Cache bleibt erhalten
- SEC/GLEIF/ESEF verwenden ebenfalls lokale Caches unter `data/cache/`
- Cache-Verzeichnis ist gitignored
- Offline-Replay bleibt im Code und in Tests, ist aber nicht mehr in der normalen Streamlit-Oberfläche sichtbar

## Neue/angepasste Tests in diesem Block

- `tests/test_esef_registry.py`
- `tests/test_gleif_provider.py`
- `tests/test_company_discovery.py`
- `tests/test_source_router.py`
- `tests/test_preferred_data.py` erweitert um semantisches SEC-Schuldengate
- `tests/test_history_mapping_audit.py`
  - stabile 10-Jahres-Serie
  - Tagwechsel als REVIEW
  - fehlendes Jahr als GAP
  - Quellen-/Währungs-/Taxonomiewechsel
  - manueller Override verdeckt die Original-Mappingserie nicht
  - ältere Jahre außerhalb des 10-Jahres-Fensters beeinflussen den Status nicht
- bestehende SEC-/ESEF-/Alpha-/Replay-Tests bleiben bestehen

**Wichtig:** Neue Tests dieses Blocks müssen lokal mit `pytest -q` ausgeführt werden. Aktueller Stand darf erst danach als grün bezeichnet werden.

## Nächster Live-Abnahmetest

1. `git pull`
2. `pytest -q`
3. `streamlit run app.py`
4. ASML R1 auf `Kennzahlen` öffnen
5. 10-Jahres-Mapping prüfen:
   - Prüffenster 2016–2025
   - Anzahl stabile Felder
   - Anzahl `prüfen`
   - Anzahl Lücken
   - auffällige Mapping-Verläufe/Wechseljahre
6. danach dieselbe Logik an weiteren Unternehmen testen:
   - Microsoft – SEC US-GAAP
   - Siemens – ESEF/IFRS, soweit Registry-Abdeckung vorhanden
   - LVMH – ESEF/IFRS, soweit Registry-Abdeckung vorhanden
7. bei Tagwechseln nicht automatisch korrigieren; zuerst fachliche Semantik/Primärquelle prüfen.

## Bekannte Grenzen / bewusst noch offen

- SEC + ESEF sind keine vollständige Weltabdeckung.
- `filings.xbrl.org` kann je Land/Jahr lückenhaft sein; fehlender Registry-Treffer ist nicht gleichbedeutend mit fehlendem Geschäftsbericht.
- Company-spezifische XBRL Extension-Tags werden derzeit nicht automatisch gemappt.
- Ein generischer automatischer Discovery-Fallback zu nationalen ESEF/OAM-Registern ist noch offen.
- Analystenschätzungen benötigen weiterhin einen separaten Provider oder manuelle Daten.
- Aktienkurs/Marktlisting und historische Rechnungslegungsdaten bleiben getrennte Aufgaben.
- ISIN/LEI/CIK/Ticker-Mapping kann weiter verbessert werden.
- Source Router mischt bewusst nicht automatisch Provider feldweise; spätere Cross-Checks können mehrere Quellen parallel speichern.
- Der 10-Jahres-Mapping-Check erkennt technische Kontinuität/Änderungen, aber erklärt einen Tagwechsel nicht automatisch als wirtschaftlich gleichwertig. Dafür bleibt semantische Prüfung erforderlich.

## Noch offene Kapitel-2-Methodik

Weiterhin Buchverifikation erforderlich:
- ROE — Kindle S. 94
- Umsatzrendite — Kindle S. 101
- Kapitalumschlag — Kindle S. 107
- Gesamtkapitalrendite — Kindle S. 109
- ROCE — Kindle S. 111
- Umsatzverdienstrate — Kindle S. 114

Keine dieser Formeln eigenmächtig festlegen.
