# Datenmodell

## Company

Stabile Unternehmensidentität.

- `id`
- `name`
- `ticker`
- `isin`
- `exchange`
- `country`
- `currency`
- `sector`
- `industry`
- `provider_symbol`

Langfristig werden Company und Listing getrennt, falls mehrere Börsenplätze/ADRs benötigt werden. Für V1 reicht das aktuelle Modell mit einem Primärlisting.

## Analysis

Eine konkrete Analyse-Revision.

- `id`
- `company_id`
- `as_of_date`
- `revision_number`
- `previous_analysis_id` optional
- `status`
- `created_at`
- `updated_at`
- `completed_at` optional
- `market_price` optional
- `market_price_currency`
- `title` optional
- `notes` optional

Eine abgeschlossene Analyse ist unveränderlicher Snapshot. Neue Daten erzeugen eine neue Revision.

## FinancialFactSnapshot

Eingefrorener **reported** Rohdatenwert pro Analyse.

- `analysis_id`
- `statement`: income/balance/cashflow/market/operating/other
- `metric`
- `period_end`
- `period_type`: FY/Q1/Q2/Q3/Q4/TTM
- `value`
- `currency`
- `unit`
- `provider`
- `source_type`: provider/company_filing/manual
- `source_url`
- `filing_date` optional
- `retrieved_at`
- `is_restated`
- `provider_field` optional
- `note` optional

Wichtig: Der gespeicherte Rohwert wird durch Analystenbereinigungen niemals überschrieben.

## FinancialAdjustmentSnapshot

Nachvollziehbare Analystenbereinigung einer veröffentlichten Zahl.

- `analysis_id`
- `metric`
- `period_end`
- `amount`
- `category`: restructuring/impairment/disposal/etc.
- `reason`
- `source_url` optional
- `included_in_normalized`
- `created_at`

`normalized value = reported value + Summe der einbezogenen Adjustments`.

Details: `docs/NORMALIZATION_POLICY.md`.

## EstimateSnapshot

Analystenkonsens strikt von Management Guidance und eigenen Annahmen getrennt.

- `analysis_id`
- `metric`
- `period`
- `low`
- `average`
- `high`
- `analyst_count`
- `provider`
- `retrieved_at`
- `currency` optional
- `unit` optional
- `note` optional

## GuidanceSnapshot

Management Guidance strikt getrennt von Analystenkonsens.

- `analysis_id`
- `metric`
- `period`
- `low`
- `high`
- `point_estimate`
- `unit`
- `currency`
- `publication_date`
- `source_url`
- `note`

## ManualInputSnapshot

Für Aktienfinder und andere manuelle Ergänzungen.

- `analysis_id`
- `metric`
- `period`
- `value`
- `unit`
- `currency`
- `source_name`
- `entered_at`
- `note`
- `overrides_metric` optional

Ein manueller Override muss in UI, Vergleich und Report sichtbar sein.

## MetricSnapshot

Berechnete Kennzahl, damit abgeschlossene Analysen vollständig reproduzierbar bleiben.

- `analysis_id`
- `metric_id`
- `period`
- `basis`: reported/normalized
- `value`
- `unit`
- `calculation_version`
- `inputs_hash` optional

Die Rohdaten bleiben zusätzlich erhalten, damit die Berechnung auditierbar ist.

## OperatingFactSnapshot

Optionale unternehmensspezifische operative Kennzahlen, die nicht zum universellen Jahresabschluss-Schema gehören.

Beispiele für ASML:
- order intake / bookings
- backlog
- net system sales
- service and field option sales
- Logic/Memory sales
- Technologie-/Systemmix

Felder:
- `analysis_id`
- `metric`
- `period`
- `value`
- `unit`
- `currency` optional
- `source_url`
- `publication_date`
- `note`

## QualitativeAssessment

- `analysis_id`
- `criterion_id`
- `rating_key`
- `rating_numeric` optional
- `comment`
- `source_note`
- `source_url` optional
- `needs_review` für übernommene Einschätzungen einer neuen Revision

## ValuationAssumption

- `analysis_id`
- `method`: fair_pe/equity_dcf/entity_dcf/etc.
- `scenario`: worst/base/best/custom
- `key`
- `value`
- `unit`
- `source_type`: analyst/guidance/manual/model/historical
- `note`

## ValuationResult

- `analysis_id`
- `method`
- `scenario`
- `metric`: equity_value/fair_value_per_share/terminal_value/etc.
- `value`
- `currency`
- `calculation_version`

## InvestmentThesis

- `analysis_id`
- `thesis_summary`
- `value_drivers`
- `risks`
- `invalidation_conditions`
- `watch_items`

## Source / Provenance-Prinzip

Jede externe Zahl muss rekonstruierbar sein:

`Analyse -> normalisierter Schlüssel -> Rohwert -> Provider-Feld/Primärquelle -> Filing/Abrufdatum`.

Providerdaten dürfen deshalb nie nur als fertige DataFrame-Zahl ohne Provenienz in der Datenbank landen.

## Warum Snapshots?

Provider ändern historische Daten, Unternehmen restaten Abschlüsse und Analystenschätzungen verändern sich. Für einen späteren Vergleich muss bekannt bleiben, was zum damaligen Analysezeitpunkt tatsächlich verwendet wurde.

Ein im Jahr 2028 neu erzeugter Report einer Analyse von 2026 verwendet ausschließlich den 2026-Snapshot.
