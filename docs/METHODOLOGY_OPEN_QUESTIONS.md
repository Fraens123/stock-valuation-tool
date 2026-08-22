# Methodology Open Questions

Hier werden fachliche Entscheidungen gesammelt, die **nicht** durch Codex oder Implementierungsdetails vorweggenommen werden dürfen.

## Vorgehen

Für jede offene Frage dokumentieren:

- Kontext
- bestehende Excel-Logik
- relevante Buchstelle / Kindle-Seite
- mögliche Varianten
- Auswirkungen auf Kennzahlen bzw. Bewertung
- endgültige Entscheidung
- Entscheidungsdatum

## Aktuell offen

### MQ-001 — Exakte Owner-Earnings-Definition im Equity-DCF

**Status:** offen

**Excel:** `Net Income + Abschreibungen - CAPEX - Δ Working Capital`.

Vor Implementierung gegen bestehendes Excel und die DCF-Stellen ab Kindle S. 295 validieren. Zu klären ist insbesondere, welche nicht zahlungswirksamen Positionen neben Abschreibungen einfließen und wie Akquisitionen behandelt werden.

### MQ-002 — DCF-Risiko-KGV vs. vollständiges faires KGV

**Status:** offen

Das Excel berechnet den Risikoaufschlag als `1 / Faires KGV`. Zu prüfen ist, welche Komponenten des fairen KGV in den Risikoaufschlag der Eigenkapitalkosten einfließen sollen, ohne Wachstum doppelt positiv zu berücksichtigen.

### MQ-003 — Risikostufen für Dropdown

**Status:** offen

Geplant: Sehr gering / Gering / Mittel / Hoch / Sehr hoch / Benutzerdefiniert. Die zugehörigen Zahlenwerte werden erst nach Buch-/Excel-Validierung festgelegt.

### MQ-004 — Analystenschätzungen im DCF

**Vorläufige Richtung:** Jahre 1–3 als Low/Consensus/High nutzen, Management-Guidance separat zeigen, danach eigene fundamentale Annahmen und Fade. Exakte Übergangslogik in Phase 8 festlegen.

### MQ-005 — Normalisierung von Sonder- und Einmaleffekten

**Status:** offen

Jahresabschlussbereinigung muss vor Fair-KGV und DCF als eigenes fachliches Konzept festgelegt werden. Relevante Kindle-Stellen: Jahresabschlussbereinigung S. 422, Pro-forma/Sondereffekte S. 427.

### MQ-006 — ROE: Jahresend-Eigenkapital oder durchschnittliches Eigenkapital

**Status:** offen / Buchprüfung erforderlich

**Excel:** `Net Income / Eigenkapital Jahresende`.

**Zielkandidat:** Jahresüberschuss / durchschnittliches Eigenkapital der Periode.

**Buch:** Kapitel 2.1, Kindle S. 94.

Die endgültige Formel wird nicht geändert, bevor die Schmidlin-Definition überprüft wurde.

### MQ-007 — Working-Capital-Laufzeiten: 360 oder 365 Tage und richtige Nenner

**Status:** methodische Korrektur vorgesehen, Buchprüfung erforderlich

**Excel Debitoren:** durchschnittliche Forderungen / Umsatz × 360.

**Excel Kreditoren:** durchschnittliche Lieferantenverbindlichkeiten / Betriebskosten × 360, weil Materialaufwand in der damaligen Morningstar-Tabelle fehlte.

**Excel DIO:** durchschnittlicher Lagerbestand / Umsatz × 360.

**Zielkandidat:**
- DSO = Ø Forderungen / Umsatz × 365
- DPO = Ø Lieferantenverbindlichkeiten / COGS bzw. Materialaufwand × 365
- DIO = Ø Vorräte / COGS × 365

**Buch:** Kapitel 4.1 / 4.6, Kindle S. 158 / 171.

### MQ-008 — Enterprise-Value-Brücke

**Status:** Korrektur erforderlich

**Excel:** `Marktkapitalisierung + Summe aller Verbindlichkeiten - liquide Mittel`.

Das setzt Gesamtverbindlichkeiten faktisch mit Marktwert des Fremdkapitals gleich. Im neuen Modell soll eine saubere Brücke mit Nettofinanzschulden und explizit definierten Zusatzpositionen verwendet werden.

**Buch:** Enterprise-Value-Ansatz Kindle S. 258.

Zu entscheiden: IFRS-16-Leasing, Pensionspositionen, Minderheiten und sonstige EV-Anpassungen.

### MQ-009 — Free Cash Flow und EV/FCF

**Status:** offen

Das Excel übernimmt an mehreren Stellen einen Morningstar-FCF und verwendet im EV/FCF zusätzlich eine spezielle Zweijahresformel. Im neuen Tool muss die FCF-Definition zentral und kapitalgeberkonsistent sein.

Zu unterscheiden:
- Equity-FCF / Owner Earnings für Equity-DCF
- FCFF für Entity-DCF bzw. EV-Multiple
- einfacher `Operating Cash Flow - Capex` als Analysekennzahl

### MQ-010 — Net Cash je Aktie

**Status:** Korrektur vorgesehen

**Excel:** `(Cash - alle Verbindlichkeiten) / Aktienzahl`.

**Ziel:** dieselbe Nettofinanzschulden-Definition wie bei Gearing/EV verwenden. Lieferantenverbindlichkeiten sollen nicht pauschal als Finanzschulden behandelt werden.

### MQ-011 — Fair-KGV-Scoring und ungehebelte Rentabilität

**Status:** Buchprüfung erforderlich

Das Excel enthält:
- Sockel-KGV
- finanzielle Stabilität
- Porter-Marktposition
- Rentabilitätsmultiplikator
- Wachstum
- Individualität

und verknüpft Marktposition × Rentabilität. Zusätzlich wird eine `Ungehebelte EKQ`-Größe verwendet. Vor Phase 6 müssen die genaue mathematische Herleitung und alle Punktebandbreiten gegen Kindle S. 351 ff. verifiziert werden.
