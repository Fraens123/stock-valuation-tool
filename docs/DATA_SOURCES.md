# Datenquellen

## Ziel

Historische Ist-Daten sollen möglichst aus **offiziellen, strukturierten und frei zugänglichen Quellen** stammen. Das Tool darf nicht von einem einzelnen kommerziellen API-Anbieter abhängen.

Alle externen Fakten werden zunächst normalisiert und mit Provenienz gespeichert. Kennzahlen und Bewertungen verwenden danach ausschließlich **Preferred Data**.

## Verbindlicher Standardablauf

```text
Unternehmen
  ↓
Identity Resolver
  ├─ Ticker / Name
  ├─ SEC CIK
  └─ GLEIF LEI
  ↓
Source Router
  ├─ 1. SEC Company Facts
  ├─ 2. ESEF / iXBRL
  └─ 3. optionaler Provider-Fallback
  ↓
Normalisierte Rohdaten
  ↓
Preferred Data / Calculation Readiness
  ↓
Kennzahlen und Bewertung
```

ASML ist ein Referenzunternehmen für Validierung, aber **keine Sonderbedingung des normalen Importpfads**.

---

## 1. SEC EDGAR / Company Facts

### Zweck

Bevorzugte historische Quelle für Unternehmen, die bei der US SEC strukturierte XBRL-Filings einreichen.

### Identität

Die SEC verwendet die **CIK (Central Index Key)**. Das Tool lädt das öffentliche Ticker-/CIK-Verzeichnis und löst Ticker bzw. bei Bedarf einen eindeutigen Unternehmensnamen auf eine CIK auf.

Gespeichert wird:
- Provider `sec`
- Purpose `cik`
- CIK getrennt vom Börsenticker

### Finanzdaten

Danach wird die öffentliche Company-Facts-JSON-Schnittstelle verwendet:

`https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`

Es ist kein API-Key erforderlich. Die SEC verlangt jedoch einen aussagekräftigen `User-Agent` mit Kontaktinformation. Dieser steht ausschließlich lokal in `.env`:

```text
SEC_USER_AGENT=Vorname Nachname email@example.com
```

### Normalisierung

Unterstützte Standardtaxonomien:
- `us-gaap`
- `ifrs-full`

Beispiele:
- `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax` → `revenue`
- `us-gaap:Assets` → `total_assets`
- `us-gaap:PropertyPlantAndEquipmentNet` → `ppe_net`
- `ifrs-full:Revenue` → `revenue`

Company-spezifische Extension-Tags werden nicht automatisch geraten.

### Wichtige Sicherheitsregel

Eine offizielle Quelle beweist die **Herkunft**, aber nicht automatisch, dass ein einzelner XBRL-Tag exakt unserer internen Definition entspricht.

Beispiel `short_term_debt`:
- unser Feld umfasst sämtliche zinstragenden Finanzschulden mit Fälligkeit <= 12 Monate,
- einschließlich Current Portion of Long-Term Debt,
- aber ohne Lieferantenverbindlichkeiten und separat behandelte Lease Liabilities.

Die SEC kann mehrere Standardkonzepte dafür verwenden. Deshalb bleibt `sec_companyfacts + short_term_debt` bis zu einem semantischen PASS bzw. bestätigten Override **nicht berechnungsbereit**.

---

## 2. GLEIF – Unternehmensidentität / LEI

GLEIF ist **keine Finanzdatenquelle**. Der öffentliche GLEIF-Dienst wird zur Identitätsauflösung verwendet:

```text
Legal Entity Name → LEI
```

Die **LEI (Legal Entity Identifier)** ist der Schlüssel für die Suche nach ESEF-Filings.

Regeln:
- keine API-Keys,
- Ergebnisse werden lokal gecacht,
- die automatische Auflösung akzeptiert nur ausreichend eindeutige Legal-Name-Matches,
- bei mehreren gleich plausiblen Rechtsträgern wird nicht geraten.

Gespeichert wird:
- Provider `gleif`
- Purpose `lei`
- LEI getrennt von Ticker, ISIN und CIK

---

## 3. ESEF / iXBRL

### Zweck

Bevorzugte strukturierte historische Quelle für geeignete europäische IFRS-Emittenten, wenn SEC keine ausreichend nutzbare Serie liefert.

### Discovery

Der Router verwendet die LEI und sucht öffentliche ESEF-Filings über `filings.xbrl.org`.

Der Dienst ist ein öffentlicher Aggregator von ESEF-Filings; die zugrunde liegenden Berichte stammen aus den regulatorischen Veröffentlichungen der Emittenten. Die Datenbank ist nicht in jedem Land/Jahr vollständig. Ein fehlender Treffer bedeutet deshalb **nicht**, dass das Unternehmen keine veröffentlichten Abschlüsse besitzt.

### Datenformat

Bevorzugt wird xBRL-JSON aus dem ESEF-Filing. Unterstützt werden zunächst nur eindeutige Standardkonzepte aus `ifrs-full`, z. B.:

- `ifrs-full:Revenue`
- `ifrs-full:ProfitLoss`
- `ifrs-full:Assets`
- `ifrs-full:Equity`
- `ifrs-full:Inventories`
- `ifrs-full:PropertyPlantAndEquipment`
- `ifrs-full:CashFlowsFromUsedInOperatingActivities`

### Sicherheitsregeln

- Nur jährliche Duration-Facts für GuV/Cashflow.
- Bilanz-Facts dürfen Instant-Facts sein.
- Facts mit zusätzlichen Segment-/Klassen-Dimensionen werden im automatischen Standardimport verworfen.
- Extension-Tags werden nicht automatisch auf interne Felder gemappt.
- Der konkrete Report-/Filing-Link wird pro Fact gespeichert, soweit verfügbar.
- Neuere Filings dürfen Restatements/Vergleichswerte für ältere Perioden liefern; Provenienz bleibt erhalten.

Der bestehende Parser für manuell hochgeladene ESEF-XHTML/ZIP-Dateien bleibt als technischer Fallback im Code.

---

## 4. Source Router

Implementiert in `src/stock_valuation/data/source_router.py`.

Der Router wählt für historische Ist-Daten zunächst **eine kohärente Quelle**:

1. SEC Company Facts
2. ESEF
3. Alpha Vantage nur wenn der Nutzer den Fallback ausdrücklich aktiviert

Er mischt nicht still einzelne Bilanzfelder von SEC mit GuV-Feldern von ESEF und Cashflow-Feldern von Alpha Vantage. Damit bleiben Rechnungslegungsbasis, Periodenlogik und Provenienz nachvollziehbar.

Eine Quelle gilt nur als automatisch nutzbar, wenn sie eine Mindestmenge an strukturierten Fakten über mindestens zwei Geschäftsjahre liefert. Fehlschläge werden protokolliert und der nächste Router-Pfad wird versucht.

---

## 5. Alpha Vantage – optionaler Fallback und Estimates

Alpha Vantage bleibt integriert, ist aber **keine Voraussetzung mehr für historische Finanzdaten**.

### Historische Daten

Nur als ausdrücklich aktivierter Fallback, wenn SEC/ESEF keine ausreichend strukturierte Quelle liefern.

Providerwerte sind nicht automatisch berechnungsbereit. Sie benötigen Primärquellenprüfung bzw. einen vorhandenen Feld-Gate.

### Analystenschätzungen

SEC und ESEF enthalten keinen Analystenkonsens. Alpha Vantage kann deshalb weiterhin separat für Estimates verwendet werden, wenn der API-Zugang funktioniert.

Der Alpha-Vantage-Cache bleibt aktiv, damit identische erfolgreiche Requests kein Tageskontingent verschwenden.

---

## 6. EODHD und weitere Provider

EODHD bleibt als vorhandener Adapter/Fallback im Code, ist aber derzeit kein Standardpfad. Weitere Anbieter werden ausschließlich hinter Provider-Interfaces und dem Source-Router-Konzept ergänzt.

Kein kommerzieller Provider darf die interne Felddefinition bestimmen.

---

## 7. ECB Data API

Für den risikofreien EUR-Zins bleibt die ECB Data API vorgesehen. Der Zins wird mit Beobachtungsdatum, Abrufdatum und genauer Serie im Analyse-Snapshot eingefroren.

---

## 8. Aktienfinder / manuelle Daten

Aktienfinder bleibt eine manuelle Ergänzungsquelle für Spezialinformationen oder Prognosen. Manuelle Overrides sind erlaubt, müssen aber Quelle, Zeitraum, Einheit/Währung und Begründung enthalten.

Ein manueller Override löscht den ursprünglichen Provider-/Primärquellenwert nicht.

---

## 9. Preferred Data und Datenqualität

Priorität bei konkurrierenden gespeicherten Fakten wird zentral in `data/resolution.py` aufgelöst. Aktuelle Reihenfolge:

1. bestätigter `manual_override`
2. vorhandene offizielle Spezial-/Referenzquelle
3. ESEF
4. SEC Company Facts
5. Alpha Vantage
6. weitere Provider

**Source Priority und Calculation Readiness sind getrennt.**

Ein Wert kann die beste vorhandene Quelle sein und trotzdem für Kennzahlen blockiert bleiben, wenn seine Semantik noch nicht ausreichend geklärt ist.

Berechnungsbereit sind insbesondere:
- bestätigte Overrides,
- eindeutig gemappte Primärquellen,
- semantisch geprüfte heikle Primärquellenfelder,
- Providerwerte mit passender Primärquellenprüfung `PASS`.

Nicht berechnungsbereit:
- ungeprüfte Providerwerte,
- `WARN`, `FAIL`, `UNKLAR` ohne bestätigten Override,
- veraltete Reviews,
- bekannte mehrdeutige XBRL-Mappings ohne semantische Freigabe,
- fertiges Provider-EBITDA, wenn EBITDA intern abgeleitet werden soll.

---

## 10. ChatGPT-Dateiprüfung

Die Prüfung über das normale ChatGPT bleibt Teil des Workflows, ändert aber ihre Rolle:

### Bei SEC/ESEF

Die Herkunft der Zahl ist bereits offiziell. ChatGPT kontrolliert vor allem:
- semantische Gleichheit von XBRL-Tag und internem Feld,
- Restatements,
- ungewöhnliche Company Extensions,
- Definitionskonflikte,
- periodische/inhaltliche Zuordnung.

### Bei Fallback-Providern

Zusätzlich wird der Zahlenwert gegen offizielle Primärquellen gegengeprüft.

Die KI verändert niemals automatisch einen gespeicherten Wert. Korrekturen werden erst durch `Übernehmen` als auditiertes Override aktiv.

---

## Grenzen

SEC + ESEF decken sehr viele, aber **nicht alle Aktien weltweit** ab. Deshalb ist die Architektur absichtlich erweiterbar:

```text
offizielle strukturierte Quelle
        ↓ falls nicht verfügbar
öffentlicher/regulatorischer Fallback
        ↓
sekundärer Datenprovider
        ↓
manuelle Ergänzung / Review
```

Das Ziel ist nicht eine behauptete universelle Einzelquelle, sondern ein universeller **Quellen-Router mit klaren Fallbacks und sichtbarer Datenqualität**.
