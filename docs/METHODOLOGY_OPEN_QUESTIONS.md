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

Vor Implementierung gegen bestehendes Excel und die DCF-Stellen im Buch validieren.

### MQ-002 — DCF-Risiko-KGV vs. vollständiges faires KGV

**Status:** offen

Zu prüfen ist, welche Komponenten des fairen KGV in den Risikoaufschlag der Eigenkapitalkosten einfließen sollen, ohne Wachstum doppelt positiv zu berücksichtigen.

### MQ-003 — Risikostufen für Dropdown

**Status:** offen

Geplant: Sehr gering / Gering / Mittel / Hoch / Sehr hoch / Benutzerdefiniert. Die zugehörigen Zahlenwerte werden erst nach Buch-/Excel-Validierung festgelegt.

### MQ-004 — Analystenschätzungen im DCF

**Vorläufige Richtung:** Jahre 1–3 als Low/Consensus/High nutzen, danach eigene fundamentale Annahmen und Fade. Exakte Übergangslogik in Phase 8 festlegen.

### MQ-005 — Normalisierung von Sonder- und Einmaleffekten

**Status:** offen

Jahresabschlussbereinigung muss vor Fair-KGV und DCF als eigenes fachliches Konzept festgelegt werden.
