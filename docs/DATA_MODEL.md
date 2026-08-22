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

## FinancialFactSnapshot

Eingefrorener Rohdatenwert pro Analyse.

- `analysis_id`
- `statement`: income/balance/cashflow/market/other
- `metric`
- `period_end`
- `period_type`: FY/FQ/TTM
- `value`
- `currency`
- `unit`
- `provider`
- `source_url`
- `retrieved_at`
- `is_restated`

## EstimateSnapshot

- `analysis_id`
- `metric`
- `period`
- `low`
- `average`
- `high`
- `analyst_count`
- `provider`
- `retrieved_at`

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

## MetricSnapshot

Berechnete Kennzahl, damit abgeschlossene Analysen vollständig reproduzierbar bleiben.

- `analysis_id`
- `metric_id`
- `period`
- `value`
- `unit`
- `calculation_version`

Die Rohdaten bleiben zusätzlich erhalten, damit die Berechnung auditierbar ist.

## QualitativeAssessment

- `analysis_id`
- `criterion_id`
- `rating_key`
- `rating_numeric` optional
- `comment`
- `source_note`
- `source_url` optional

## ValuationAssumption

- `analysis_id`
- `method`: fair_pe/equity_dcf/entity_dcf/etc.
- `scenario`: worst/base/best/custom
- `key`
- `value`
- `unit`
- `source_type`: analyst/guidance/manual/model
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

## Warum Snapshots?

Provider ändern historische Daten, Unternehmen restaten Abschlüsse und Analystenschätzungen verändern sich. Für einen späteren Vergleich muss bekannt bleiben, was zum damaligen Analysezeitpunkt tatsächlich verwendet wurde.
