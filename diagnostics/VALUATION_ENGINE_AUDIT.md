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

## Quality Context Integration

- Business Quality is loaded from overall_quality_score plus component scores.
- Quality context is persisted for review and provenance only.
- Quality does not change DCF cash flows, discount rates, fair values, or multiples.

## Historical Context Integration

- Historical Analysis is loaded as read-only context for Phase 7.
- Included context covers growth, CAGR, margin trends, volatility, negative years, and missing years where available.
- Historical context does not derive or modify DCF assumptions in V1.

## Warning Propagation

- Non-blocking upstream warnings are propagated through DCF and final Valuation Summary.
- OUTLIER_REVIEW remains visible when normalized inputs are still usable.
- Generic V1 DCF assumptions are marked with ASSUMPTIONS_NOT_COMPANY_SPECIFIC.

## Valuation Snapshot Architecture

- Each company receives an immutable ValuationSnapshot payload in the JSON audit.
- Snapshot identity is deterministic from analysis_id, analysis date, market_snapshot_id, assumptions_hash, inputs_hash, and valuation version.
- Same inputs and assumptions produce the same reproducibility hash; changed inputs produce a new snapshot.

## Market Snapshot Linkage

- Diagnostics derive a deterministic market_snapshot_id from ticker, analysis date, market input hashes, and market data version.
- Production callers can provide a persistent market_snapshot_id through MarketSnapshotInput.

## Assumption Snapshot

- Bear/Base/Bull assumptions are stored inside every valuation snapshot.
- The default V1 assumptions are marked as GENERIC_V1_DEFAULT, not company-specific forecasts.

## Generic vs Company-Specific Assumptions

- Current V1 DCF values are available but carry ASSUMPTIONS_NOT_COMPANY_SPECIFIC.
- Company-specific assumption derivation is reserved for Phase 7.

## Persistence / Immutability

- valuation_snapshot_results.csv records market_snapshot_id, valuation_snapshot_id, assumptions_hash, and inputs_hash.
- No old valuation result is overwritten in the snapshot model; new inputs create new deterministic snapshot identities.

## Companies

### ASML

- Latest fiscal year used: FY2025
- Market snapshot ID: c21bae2ef59abe4e07ebf74fd6a7269bdba02514ec13a8f8a5db36e90246bdaf
- Valuation snapshot ID: ad21a2cce849fa4e5db2a1dfc957a48b59f246f345d8bcd7d498e27f153e512d
- Normalized FCF: 9099000000.0 EUR
- Normalization issues: OUTLIER_REVIEW
- Quality score: 8.033333333333333333333333333
- Quality assessment: STRONG
- Historical context availability: True
- DCF assumption source: GENERIC_V1_DEFAULT
- Bear assumptions: {'scenario': 'bear', 'projection_years': 5, 'annual_growth_rate': Decimal('0.02'), 'discount_rate': Decimal('0.10'), 'terminal_growth_rate': Decimal('0.01'), 'assumption_source': 'GENERIC_V1_DEFAULT'}
- Base assumptions: {'scenario': 'base', 'projection_years': 5, 'annual_growth_rate': Decimal('0.05'), 'discount_rate': Decimal('0.09'), 'terminal_growth_rate': Decimal('0.02'), 'assumption_source': 'GENERIC_V1_DEFAULT'}
- Bull assumptions: {'scenario': 'bull', 'projection_years': 5, 'annual_growth_rate': Decimal('0.08'), 'discount_rate': Decimal('0.08'), 'terminal_growth_rate': Decimal('0.03'), 'assumption_source': 'GENERIC_V1_DEFAULT'}
- Bear fair value: 323.2172186653062540712377426 USD
- Base fair value: 457.4476004093199578215331287 USD
- Bull fair value: 707.0510236213485440528523777 USD
- Market price: 1763.7600 USD
- Base upside/downside: -0.7406406765039914966766832626
- Base margin of safety: -2.855654720719495680687145223
- Warnings: ASSUMPTIONS_NOT_COMPANY_SPECIFIC, OUTLIER_REVIEW
- Inputs hash: efe78bc04e1e7f66c770a3bc5b94ffe33b19a96760e98db8a782cea02c260e65
- Statuses: AVAILABLE

### AAPL

- Latest fiscal year used: FY2025
- Market snapshot ID: 17d2091c7c905f7089ab7e8bbf00d7be6b7d9e766343c7fb080c04848ab8b004
- Valuation snapshot ID: 47657d43d0046c7b2fe24772230db6a354f1f2408bb608e22874a6ca0d4eb864
- Normalized FCF: 99584000000.0 USD
- Normalization issues: None
- Quality score: 7.707323658043125340595157266
- Quality assessment: SOLID
- Historical context availability: True
- DCF assumption source: GENERIC_V1_DEFAULT
- Bear assumptions: {'scenario': 'bear', 'projection_years': 5, 'annual_growth_rate': Decimal('0.02'), 'discount_rate': Decimal('0.10'), 'terminal_growth_rate': Decimal('0.01'), 'assumption_source': 'GENERIC_V1_DEFAULT'}
- Base assumptions: {'scenario': 'base', 'projection_years': 5, 'annual_growth_rate': Decimal('0.05'), 'discount_rate': Decimal('0.09'), 'terminal_growth_rate': Decimal('0.02'), 'assumption_source': 'GENERIC_V1_DEFAULT'}
- Bull assumptions: {'scenario': 'bull', 'projection_years': 5, 'annual_growth_rate': Decimal('0.08'), 'discount_rate': Decimal('0.08'), 'terminal_growth_rate': Decimal('0.03'), 'assumption_source': 'GENERIC_V1_DEFAULT'}
- Bear fair value: 79.85342844534233128473435739 USD
- Base fair value: 113.0161300738280732269426081 USD
- Bull fair value: 174.6826748745047683391598569 USD
- Market price: 309.3500 USD
- Base upside/downside: -0.6346658151807723509715771518
- Base margin of safety: -1.737219897707666409686777004
- Warnings: ASSUMPTIONS_NOT_COMPANY_SPECIFIC
- Inputs hash: def0c3cd15aed310a4497bddd60fc0f3f4a0efdfa2f6d41b14883db8c5d11555
- Statuses: AVAILABLE

### MSFT

- Latest fiscal year used: FY2026
- Market snapshot ID: 5790bd4e7777a39768a574a27421c72fa62640b2c10217e494e17c7f19ee7aa0
- Valuation snapshot ID: 66699ddacc3d0bd476e26ebcdedf46ca218637df6d4b28e47beb90f482595bf8
- Normalized FCF: 71611000000.0 USD
- Normalization issues: None
- Quality score: 7.971099601711631218802991919
- Quality assessment: SOLID
- Historical context availability: True
- DCF assumption source: GENERIC_V1_DEFAULT
- Bear assumptions: {'scenario': 'bear', 'projection_years': 5, 'annual_growth_rate': Decimal('0.02'), 'discount_rate': Decimal('0.10'), 'terminal_growth_rate': Decimal('0.01'), 'assumption_source': 'GENERIC_V1_DEFAULT'}
- Base assumptions: {'scenario': 'base', 'projection_years': 5, 'annual_growth_rate': Decimal('0.05'), 'discount_rate': Decimal('0.09'), 'terminal_growth_rate': Decimal('0.02'), 'assumption_source': 'GENERIC_V1_DEFAULT'}
- Bull assumptions: {'scenario': 'bull', 'projection_years': 5, 'annual_growth_rate': Decimal('0.08'), 'discount_rate': Decimal('0.08'), 'terminal_growth_rate': Decimal('0.03'), 'assumption_source': 'GENERIC_V1_DEFAULT'}
- Bear fair value: 112.8587079767950777712797663 USD
- Base fair value: 159.7283256209848066298604577 USD
- Bull fair value: 246.8830878784525380534093882 USD
- Market price: 483.2400 USD
- Base upside/downside: -0.6694637744785514306972509360
- Base margin of safety: -2.025387000842090082028852508
- Warnings: ASSUMPTIONS_NOT_COMPANY_SPECIFIC
- Inputs hash: c87237e3441acab36ca17f792a08d761a2b5fb2ef41c1c233df53c8b194bb0c3
- Statuses: AVAILABLE

### TSM

- Latest fiscal year used: FY2025
- Market snapshot ID: 09ef981fd9e4dbc2167fa46ab1c32b903ed20d56dd059f5a876762db4c8fa02f
- Valuation snapshot ID: 3aea274e1ba0e2e1e2f8c41d5c1d7ce2be9e9e892fe1468aa4cb9227c89a1f6c
- Normalized FCF: 870170600000.0 TWD
- Normalization issues: OUTLIER_REVIEW
- Quality score: 8.266973142126208103773367806
- Quality assessment: STRONG
- Historical context availability: True
- DCF assumption source: GENERIC_V1_DEFAULT
- Bear assumptions: {'scenario': 'bear', 'projection_years': 5, 'annual_growth_rate': Decimal('0.02'), 'discount_rate': Decimal('0.10'), 'terminal_growth_rate': Decimal('0.01'), 'assumption_source': 'GENERIC_V1_DEFAULT'}
- Base assumptions: {'scenario': 'base', 'projection_years': 5, 'annual_growth_rate': Decimal('0.05'), 'discount_rate': Decimal('0.09'), 'terminal_growth_rate': Decimal('0.02'), 'assumption_source': 'GENERIC_V1_DEFAULT'}
- Bull assumptions: {'scenario': 'bull', 'projection_years': 5, 'annual_growth_rate': Decimal('0.08'), 'discount_rate': Decimal('0.08'), 'terminal_growth_rate': Decimal('0.03'), 'assumption_source': 'GENERIC_V1_DEFAULT'}
- Bear fair value: 61.70048788239865302957210454 USD
- Base fair value: 87.32437041083045706445959627 USD
- Bull fair value: 134.9723671756515756617261428 USD
- Market price: 418.9500 USD
- Base upside/downside: -0.7915637417094391763588504684
- Base margin of safety: -3.797629779968496362120676224
- Warnings: ASSUMPTIONS_NOT_COMPANY_SPECIFIC, OUTLIER_REVIEW
- Inputs hash: 02c0a4d73d546664b0ef8475bdc280370ce25699f90c7b3243e49b4ccf0ee3d3
- Statuses: AVAILABLE

### ADBE

- Latest fiscal year used: FY2025
- Market snapshot ID: c9e720a6e941f94f1da3c9aaa54108e6fd3cd0da4b527249b3527357d3f3f61b
- Valuation snapshot ID: aae1131dc90dc2437b39e562f6d22f9478ee06151027cd31a21ad46e9091cd52
- Normalized FCF: 7873000000.0 USD
- Normalization issues: None
- Quality score: 8.255825793366261170620653158
- Quality assessment: STRONG
- Historical context availability: True
- DCF assumption source: GENERIC_V1_DEFAULT
- Bear assumptions: {'scenario': 'bear', 'projection_years': 5, 'annual_growth_rate': Decimal('0.02'), 'discount_rate': Decimal('0.10'), 'terminal_growth_rate': Decimal('0.01'), 'assumption_source': 'GENERIC_V1_DEFAULT'}
- Base assumptions: {'scenario': 'base', 'projection_years': 5, 'annual_growth_rate': Decimal('0.05'), 'discount_rate': Decimal('0.09'), 'terminal_growth_rate': Decimal('0.02'), 'assumption_source': 'GENERIC_V1_DEFAULT'}
- Bull assumptions: {'scenario': 'bull', 'projection_years': 5, 'annual_growth_rate': Decimal('0.08'), 'discount_rate': Decimal('0.08'), 'terminal_growth_rate': Decimal('0.03'), 'assumption_source': 'GENERIC_V1_DEFAULT'}
- Bear fair value: 231.7857952637011854793916799 USD
- Base fair value: 328.0451960145746500087432435 USD
- Bull fair value: 507.0410062893081761006289308 USD
- Market price: 275.3000 USD
- Base upside/downside: 0.191591703649017980416793474
- Base margin of safety: 0.1607863692423383177690540024
- Warnings: ASSUMPTIONS_NOT_COMPANY_SPECIFIC
- Inputs hash: 9414e5367fe0d45ae61cd183b4e7a742c42b126b0e348f0c522fa9db495f8c49
- Statuses: AVAILABLE

## Regression Results

- Valuation snapshot, context, warning propagation, and deterministic hash tests are covered by tests/test_valuation_engine.py.
## Blockers

- None.

## Artifacts

- diagnostics/valuation_results.csv
- diagnostics/dcf_sensitivity.csv
- diagnostics/valuation_snapshot_results.csv
- diagnostics/VALUATION_ENGINE_AUDIT.json
