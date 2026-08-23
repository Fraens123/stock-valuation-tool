# VALUATION ASSUMPTION ENGINE AUDIT

Decision: **NO-GO – ASSUMPTION APPROVAL REQUIRED**

## 1. Executive Summary

- Phase 7 creates deterministic assumption recommendations and preview valuations.
- Recommendations are not automatically approved.
- Frozen Valuation Engine V1 is reused for preview; DCF math is not duplicated.

## 2. Input Layers

- VALUATION_ENGINE_AUDIT.json
- valuation_results.csv
- valuation_snapshot_results.csv
- market_data_live_results.csv

## 3. Evidence Model

- Evidence is separated into historical growth, margin, volatility, quality context, and optional forward evidence.

## 4. Policy Model

- All interpretation rules are marked PROJECT_POLICY_V1.

## 5. Recommendation vs Approval

- Recommendations can be REVIEW_REQUIRED and are not silently promoted to approved assumptions.

## 6. FCF Base Policy

- Base FCF uses frozen normalized_fcf only.
- OUTLIER_REVIEW and PARTIAL_NORMALIZATION_WINDOW require review but do not discard FCF.

## 7. Historical Growth Evidence

- Revenue, earnings, and FCF growth are tracked separately.
- The engine does not average different growth metrics into one mixed anchor.

## 8. Forward Estimates / Guidance

- Supported as point-in-time evidence when persisted; diagnostics found no approved forward evidence in current CSV artifacts.

## 9. Margin Context

- Operating, EBITDA, and FCF margin trend/volatility are retained as context and warnings.

## 10. Volatility / Cyclicality

- High FCF volatility triggers CYCLICALITY_REVIEW and lowers confidence.

## 11. Business Quality Context

- Quality can affect confidence/review context only; it does not change growth, discount rate, or fair value directly.

## 12. Discount Rate / Cost of Equity Policy

- Equity DCF requires Cost of Equity, not WACC.
- Missing beta/ERP are not imputed; generic fallback requires review.

## 13. Terminal Growth Policy

- Terminal growth is not copied from company CAGR.
- Generic terminal growth requires review unless manually/macro approved.

## 14. Scenario Construction

- Bear/Base/Bull growth uses historical distribution policy.
- Discount rate ordering is Bear >= Base >= Bull.
- Preview fair value ordering is checked through Frozen Valuation Engine V1.

## 15. Point-in-Time Rules

- Guidance after analysis_as_of_date is LOOKAHEAD_BLOCKED.
- Estimates retrieved after analysis_as_of_date are LOOKAHEAD_BLOCKED.

## 16. ASML

- normalized FCF: 9099000000.0
- FCF base assessment: REVIEW_REQUIRED
- growth primary anchor: historical FCF CAGR
- base growth recommendation: 0.15
- base discount rate: 0.09
- base terminal growth: 0.02
- projection years: 5
- confidence: LOW
- review required: True
- warnings: FCF_BASE_OUTLIER_REVIEW, GROWTH_SUSTAINABILITY_REVIEW, DISCOUNT_RATE_NOT_COMPANY_SPECIFIC, REQUIRED_RETURN_REVIEW, TERMINAL_GROWTH_GENERIC
- preview fair value bear/base/bull: 504.3974562703527790970449242 / 688.7467287051706002747075539 / 1025.666296051545578915451804
- generic base fair value: 457.4476004093199578215331287
- company-specific preview base delta: 231.2991282958506424531744252

## 17. AAPL

- normalized FCF: 99584000000.0
- FCF base assessment: RECOMMENDED
- growth primary anchor: historical FCF CAGR
- base growth recommendation: -0.0041105127462073124059693268
- base discount rate: 0.09
- base terminal growth: 0.02
- projection years: 5
- confidence: LOW
- review required: True
- warnings: DISCOUNT_RATE_NOT_COMPANY_SPECIFIC, REQUIRED_RETURN_REVIEW, TERMINAL_GROWTH_GENERIC
- preview fair value bear/base/bull: 66.25133802711663097653718412 / 89.53884421494522492635449885 / 132.0138409527250141466272023
- generic base fair value: 113.0161300738280732269426081
- company-specific preview base delta: -23.47728585888284830058810925

## 18. MSFT

- normalized FCF: 71611000000.0
- FCF base assessment: RECOMMENDED
- growth primary anchor: historical FCF CAGR
- base growth recommendation: -0.0490204886411655672343833440
- base discount rate: 0.09
- base terminal growth: 0.02
- projection years: 5
- confidence: LOW
- review required: True
- warnings: DISCOUNT_RATE_NOT_COMPANY_SPECIFIC, REQUIRED_RETURN_REVIEW, TERMINAL_GROWTH_GENERIC
- preview fair value bear/base/bull: 77.04907753514319096329488946 / 103.6575177615198450180119132 / 152.1338015855840646135550683
- generic base fair value: 159.7283256209848066298604577
- company-specific preview base delta: -56.0708078594649616118485445

## 19. TSM

- normalized FCF: 870170600000.0
- FCF base assessment: REVIEW_REQUIRED
- growth primary anchor: historical FCF CAGR
- base growth recommendation: 0.15
- base discount rate: 0.09
- base terminal growth: 0.02
- projection years: 5
- confidence: LOW
- review required: True
- warnings: FCF_BASE_OUTLIER_REVIEW, GROWTH_SUSTAINABILITY_REVIEW, DISCOUNT_RATE_NOT_COMPANY_SPECIFIC, REQUIRED_RETURN_REVIEW, TERMINAL_GROWTH_GENERIC
- preview fair value bear/base/bull: 96.28685398332139594322319785 / 131.4781723696472159834503345 / 195.7943674295528410020876367
- generic base fair value: 87.32437041083045706445959627
- company-specific preview base delta: 44.15380195881675891899073823

## 20. ADBE

- normalized FCF: 7873000000.0
- FCF base assessment: RECOMMENDED
- growth primary anchor: historical FCF CAGR
- base growth recommendation: 0.15
- base discount rate: 0.09
- base terminal growth: 0.02
- projection years: 5
- confidence: LOW
- review required: True
- warnings: GROWTH_SUSTAINABILITY_REVIEW, DISCOUNT_RATE_NOT_COMPANY_SPECIFIC, REQUIRED_RETURN_REVIEW, TERMINAL_GROWTH_GENERIC
- preview fair value bear/base/bull: 361.7139149126675894746433283 / 493.9146154014484910458359273 / 735.5266501184098144265859150
- generic base fair value: 328.0451960145746500087432435
- company-specific preview base delta: 165.8694193868738410370926838

## 21. Generic vs Company-Specific Preview

- Preview values use recommended assumptions and are marked ASSUMPTION_PREVIEW.

## 22. Review Required Cases

- ASML: FCF_BASE_OUTLIER_REVIEW,GROWTH_SUSTAINABILITY_REVIEW,DISCOUNT_RATE_NOT_COMPANY_SPECIFIC,REQUIRED_RETURN_REVIEW,TERMINAL_GROWTH_GENERIC
- AAPL: DISCOUNT_RATE_NOT_COMPANY_SPECIFIC,REQUIRED_RETURN_REVIEW,TERMINAL_GROWTH_GENERIC
- MSFT: DISCOUNT_RATE_NOT_COMPANY_SPECIFIC,REQUIRED_RETURN_REVIEW,TERMINAL_GROWTH_GENERIC
- TSM: FCF_BASE_OUTLIER_REVIEW,GROWTH_SUSTAINABILITY_REVIEW,DISCOUNT_RATE_NOT_COMPANY_SPECIFIC,REQUIRED_RETURN_REVIEW,TERMINAL_GROWTH_GENERIC
- ADBE: GROWTH_SUSTAINABILITY_REVIEW,DISCOUNT_RATE_NOT_COMPANY_SPECIFIC,REQUIRED_RETURN_REVIEW,TERMINAL_GROWTH_GENERIC

## 23. Tests

- tests/test_valuation_assumption_engine.py covers policy separation, growth anchors, point-in-time rules, discount/terminal safeguards, quality non-multiplication, and preview ordering.

## 24. GO / NO-GO

- NO-GO – ASSUMPTION APPROVAL REQUIRED

## Deferred

- automatic CAPM
- automatic beta
- automatic equity risk premium
- automatic WACC
- macro-derived terminal growth
- sector-specific valuation frameworks
- bank/insurance valuation
- cycle timing
