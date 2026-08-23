# VALUATION ENGINE AUDIT

Decision: **GO – VALUATION ENGINE V1 FROZEN**

## Scope

- New Valuation Engine V1 reads frozen CSV artifacts only.
- No direct provider, HTTP, raw SEC, EdgarTools, or market API access is used.
- Equity DCF does not subtract net debt; EV-based current multiples use enterprise value.
- No BUY/SELL/HOLD recommendation is generated.

## Methods

- Current market multiples: P/E, EV/EBIT, EV/EBITDA, P/FCF, earnings yield, FCF yield.
- Normalized earnings/cash flow: three-year median selected; average and weighted average are implemented alternatives.
- Equity DCF scenarios: Bear/Base/Bull with explicit centralized assumptions.
- Summary: fair value per listed ordinary/ADR/ADS unit, upside/downside, margin of safety.

## Companies

### ASML

- Latest fiscal year used: FY2025
- Statuses: AVAILABLE

### AAPL

- Latest fiscal year used: FY2025
- Statuses: AVAILABLE

### MSFT

- Latest fiscal year used: FY2026
- Statuses: AVAILABLE

### TSM

- Latest fiscal year used: FY2025
- Statuses: AVAILABLE

### ADBE

- Latest fiscal year used: FY2025
- Statuses: AVAILABLE

## Blockers

- None.

## Artifacts

- diagnostics/valuation_results.csv
- diagnostics/dcf_sensitivity.csv
- diagnostics/VALUATION_ENGINE_AUDIT.json
