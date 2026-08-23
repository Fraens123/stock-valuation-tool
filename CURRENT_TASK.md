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

### 3. SEC-Historienpipeline

Generischer Ablauf:

```text
SEC Company Facts
  ↓ Lücke im 10-Jahres-Fenster
Originales 10-K / 20-F / 40-F
  ↓
Standard-XBRL sicher? → sec_filing_xbrl
  ↓ nein
Company-Extension-XBRL plausibel? → Review-Kandidat
  ↓ nein
Offizielle Filing-Tabelle nach eindeutig beschrifteter Zeile durchsuchen
  ↓
Tabellenkandidat → bestehender sec_filing_extension-Reviewpfad
  ↓
ChatGPT-Semantikprüfung
  ├─ PASS → berechnungsbereit
  ├─ FAIL + sicherer offizieller Wert → Nutzer kann Override übernehmen
  └─ UNKLAR → blockiert
```

Schutzregeln:
- keine fehlende Zahl wird als Null erfunden,
- Company Facts gewinnt bei gleichem Feld/Zeitraum,
- Standard-XBRL gewinnt vor Review-Kandidaten,
- Tabellen-/Extension-Kandidaten bleiben bis PASS blockiert,
- `short_term_debt` wird nicht blind aus einem Einzelwert oder beliebigen Komponenten abgeleitet,
- Tabelle muss eine stark passende Beschriftung besitzen; Jahr und erkannte Skalierung bleiben in der Provenienz,
- SEC-Dokumente werden lokal gecacht.

### 4. ESEF

- LEI über GLEIF
- Filings über `filings.xbrl.org`
- Standardkonzepte aus `ifrs-full`
- dimensionale Facts und Extensions werden nicht still als Konzernwerte übernommen
- konkrete Filing-/Report-URL bleibt als Provenienz erhalten

### 5. Preferred Data

- Source Resolution und Calculation Readiness sind getrennt.
- manuelle Overrides bleiben höchste Korrekturebene.
- Primärquelle allein genügt bei semantisch mehrdeutigen Feldern nicht automatisch.
- SEC-Filing-Kandidaten werden erst nach exakt passendem Review-PASS calculation-ready.

### 6. ChatGPT-Dateiprüfung

- 2/3/5 aktuelle Geschäftsjahre werden vollständig geprüft,
- ältere offene `sec_filing_extension`-Kandidaten aus dem 10-Jahres-Fenster werden automatisch angehängt,
- der Nutzer muss nicht 10 vollständige Jahre tief prüfen,
- PASS nur bei gleicher wirtschaftlicher Semantik,
- sichere Abweichungen können als auditiertes Override übernommen werden.

### 7. 10-Jahres-Mapping-Check

`src/stock_valuation/data/history_mapping_audit.py`

Prüft automatisch und ohne Netzwerk:
- 10-Jahres-Abdeckung,
- Originalfeld/XBRL-Tag,
- Quellenfamilie,
- Währung,
- Taxonomie,
- echte mehrere Geschäftsjahresenden.

Status:
- `PASS`: vollständig und technisch/fachlich aufgelöst,
- `REVIEW`: vollständig, aber Mappingänderung noch nicht fachlich bestätigt,
- `GAP`: mindestens ein Jahr ohne brauchbaren Kandidaten/Wert.

### 8. Finanzdaten-UX – verbindlicher Workflow

Der gesamte Datenworkflow bleibt auf **einer Seite `Finanzdaten`**:

1. Finanzdaten laden / aktualisieren
2. kompakter Datenstatus
3. 10-Jahres-Abdeckung und technische Details nur in Expandern
4. ChatGPT-Prüfpaket herunterladen / Ergebnis wieder einlesen
5. Korrekturvorschläge entscheiden
6. manuelle Korrekturen nur bei Bedarf
7. Analystenschätzungen optional

`Kennzahlen` enthält keine Import-/Mappingarbeit mehr, sondern nur Analyseergebnisse und automatisch synchronisierte Kennzahlen.

Die Statusanzeige unterscheidet ausdrücklich zwischen:
- fehlenden historischen Jahren,
- gespeicherten aber blockierten Werten,
- lokaler Plausibilität,
- berechnungsbereiten Preferred-Data-Werten.

Die frühere irreführende Kennzahl `Missing` wird im normalen Status nicht mehr verwendet; leere gespeicherte Werte stehen nur noch in technischen Details.

### 9. Cache / Entwicklung

- Alpha Vantage, SEC, SEC-Filings, GLEIF und ESEF verwenden lokale Caches unter `data/cache/`,
- Cache ist gitignored,
- Offline-Replay bleibt nur im Code/Test und ist aus der normalen UI entfernt.

## Neue/angepasste Tests dieses Blocks

- `tests/test_sec_filing_text_candidates.py`
  - Zieljahresspalte wird verwendet
  - Tabellen-Skalierung (z. B. EUR in Millionen) wird berücksichtigt
  - vorgeschlagene Dividende wird nicht mit gezahlter Dividende verwechselt
- `tests/test_sec_history_completion.py`
  - noch fehlende 10-Jahreswerte werden als Review-Kandidaten in den bestehenden SEC-Filing-Reviewpfad eingespeist

Bestehende SEC-/ESEF-/Router-/Preferred-Data-/History-/Review-Tests bleiben verbindlich.

**Wichtig:** Dieser Stand darf erst nach lokalem `pytest -q` als grün bezeichnet werden.

## Nächster Live-Abnahmetest

1. `git pull`
2. `pytest -q`
3. `streamlit run app.py`
4. ASML R1 → `Finanzdaten` → `Finanzdaten laden / aktualisieren`
5. Auf derselben Seite den neuen **Datenstatus** prüfen.
6. Wenn Filing-Tabellenkandidaten gefunden wurden, normales Prüfpaket mit **3 Jahren** herunterladen; ältere Kandidaten müssen automatisch enthalten sein.
7. JSON wieder importieren.
8. Ziel: Datenstatus zeigt entweder `Datenbasis bereit für die Analyse` oder benennt nur noch tatsächlich nicht belegbare Restlücken.
9. Danach dieselbe Architektur an mindestens einem weiteren SEC-Unternehmen und anschließend einem ESEF-Unternehmen testen.

## Bewusst offene Grenzen

- SEC + ESEF sind keine vollständige Weltabdeckung.
- Ein Tabellen-/Extension-Kandidat kann trotz guter Beschriftung wirtschaftlich zu eng oder zu breit sein; deshalb bleibt der Review zwingend.
- Wenn weder Standard-XBRL, Extension-XBRL noch eine ausreichend eindeutige Filing-Tabelle einen Kandidaten liefern, bleibt der Wert offen statt erfunden zu werden.
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
