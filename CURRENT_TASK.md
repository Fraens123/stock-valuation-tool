# Current Task

## Nächster Entwicklungsblock: Phase 0 – Application Foundation fertigstellen

Vor Beginn lesen:
- `AGENTS.md`
- `ROADMAP.md`
- `docs/ARCHITECTURE.md`
- `docs/ANALYSIS_LIFECYCLE.md`
- `docs/DATA_MODEL.md`

## Ziel

Das Grundsystem soll funktionieren, bevor Finanzdaten und Bewertungsformeln eingebaut werden.

## Aufgaben

1. Bestehenden Phase-0-Code prüfen und Fehler beheben.
2. Company-Service vervollständigen.
3. Analyse öffnen/bearbeiten.
4. Statuswechsel `draft -> in_progress -> completed` implementieren.
5. Abgeschlossene Analyse gegen Änderungen sperren.
6. `Neue Revision erstellen` implementieren:
   - neue Analysis-Zeile
   - `previous_analysis_id`
   - neue Revisionsnummer
   - übernehmbare qualitative/persönliche Daten später über klaren Copy-Service vorbereiten
7. Basis-Vergleich zweier Analysis-Revisionen implementieren.
8. vorhandenen PDF-Prototyp in der UI als Download für die gewählte Analyse anbinden.
9. Tests für Lifecycle und Freeze-Verhalten ergänzen.
10. `ROADMAP.md` nur für tatsächlich fertige Punkte aktualisieren.

## Noch ausdrücklich NICHT tun

- keine DCF-Formeln implementieren
- keine Fair-KGV-Logik erfinden
- keine Risiko-Stufenwerte festlegen
- keine produktive EODHD-Normalisierung implementieren
- keine Buchtexte kopieren

## Definition of Done

Lokal kann der Nutzer:
1. ASML anlegen,
2. eine Analyse erstellen,
3. sie bearbeiten und abschließen,
4. eine neue Revision erzeugen,
5. beide Revisionen auswählen/vergleichen,
6. einen einfachen PDF-Snapshot herunterladen.

Danach wechseln wir zu **Phase 1: vollständige fachliche Inventarisierung des Excel-Modells**.
