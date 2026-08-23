# SEMANTIC_GATE_PRODUCTION_AUDIT

## 1. Policy
Version: `semantic-policy-v1.0`

Priority:
1. confirmed manual override
2. exact matching explicit review PASS
3. versioned SAFE_STANDARD_MAPPING
4. otherwise REVIEW_REQUIRED

## 2. Safe Standard Mappings
- depreciation_amortization sec_companyfacts `aggregation:ifrs-full:DepreciationExpense+ifrs-full:AmortisationExpense`: Complete IFRS component aggregate: depreciation expense plus amortisation expense.
- depreciation_amortization sec_companyfacts `aggregation:us-gaap:Depreciation+us-gaap:AmortizationOfIntangibleAssets`: Complete US-GAAP component aggregate: tangible depreciation plus intangible amortization.
- short_term_debt sec_companyfacts `aggregation:us-gaap:ShortTermBorrowings+us-gaap:LongTermDebtCurrent`: Complete US-GAAP short-term debt aggregate: short-term borrowings plus current long-term debt.
- short_term_debt sec_companyfacts `ifrs-full:CurrentBorrowings`: IFRS current borrowings total; interest-bearing current financing by taxonomy definition.
- depreciation_amortization sec_companyfacts `ifrs-full:DepreciationAndAmortisationExpense`: IFRS combined depreciation and amortisation expense concept.
- ppe_net sec_companyfacts `ifrs-full:PropertyPlantAndEquipment`: IFRS property, plant and equipment carrying amount; ROU assets stay separately tagged when separately reported.
- short_term_debt sec_companyfacts `us-gaap:DebtCurrent`: US-GAAP current debt total; excludes trade payables by taxonomy definition.
- depreciation_amortization sec_companyfacts `us-gaap:DepreciationAndAmortization`: US-GAAP combined depreciation and amortization concept without depletion or catch-all wording.
- ppe_net sec_companyfacts `us-gaap:PropertyPlantAndEquipmentNet`: US-GAAP net property, plant and equipment standard concept.

## 3. Provider Field Combinations
- AAPL depreciation_amortization sec_companyfacts `us-gaap:DepreciationAndAmortization`: years=2008 2009 2010 2011 2012 2013 2014, ready=2008 2009 2010 2011 2012 2013 2014, pending=-, decision=SAFE_STANDARD_MAPPING
- AAPL depreciation_amortization sec_companyfacts `us-gaap:DepreciationDepletionAndAmortization`: years=2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025, ready=-, pending=2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025, decision=REVIEW_REQUIRED
- AAPL ppe_net sec_companyfacts `us-gaap:PropertyPlantAndEquipmentNet`: years=2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025, ready=2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025, pending=-, decision=SAFE_STANDARD_MAPPING
- AAPL short_term_debt sec_companyfacts `aggregation:us-gaap:LongTermDebtCurrent`: years=2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025, ready=-, pending=2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025, decision=REVIEW_REQUIRED
- ADBE depreciation_amortization sec_companyfacts `us-gaap:DepreciationAndAmortization`: years=2007 2008, ready=2007 2008, pending=-, decision=SAFE_STANDARD_MAPPING
- ADBE depreciation_amortization sec_companyfacts `us-gaap:DepreciationDepletionAndAmortization`: years=2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025, ready=-, pending=2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025, decision=REVIEW_REQUIRED
- ADBE ppe_net sec_companyfacts `us-gaap:PropertyPlantAndEquipmentNet`: years=2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025, ready=2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025, pending=-, decision=SAFE_STANDARD_MAPPING
- ADBE short_term_debt sec_companyfacts `us-gaap:DebtCurrent`: years=2018 2019 2020 2021 2022 2023 2024 2025, ready=2018 2019 2020 2021 2022 2023 2024 2025, pending=-, decision=SAFE_STANDARD_MAPPING
- ADBE short_term_debt sec_filing_extension `company-extension:AdjustedCarryingValueofSeniorLongTermNotes`: years=2016, ready=-, pending=2016, decision=REVIEW_REQUIRED
- ASML depreciation_amortization sec_companyfacts `us-gaap:DepreciationAndAmortization`: years=2007 2008 2009 2010 2011, ready=2007 2008 2009 2010 2011, pending=-, decision=SAFE_STANDARD_MAPPING
- ASML depreciation_amortization sec_companyfacts `us-gaap:DepreciationDepletionAndAmortization`: years=2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025, ready=-, pending=2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025, decision=REVIEW_REQUIRED
- ASML ppe_net sec_companyfacts `us-gaap:PropertyPlantAndEquipmentNet`: years=2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025, ready=2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025, pending=-, decision=SAFE_STANDARD_MAPPING
- ASML short_term_debt sec_companyfacts `aggregation:us-gaap:LongTermDebtCurrent`: years=2010 2011 2012 2013 2014 2018 2019 2020 2021 2022 2023 2024 2025, ready=-, pending=2010 2011 2012 2013 2014 2018 2019 2020 2021 2022 2023 2024 2025, decision=REVIEW_REQUIRED
- MSFT depreciation_amortization sec_companyfacts `aggregation:us-gaap:Depreciation+us-gaap:AmortizationOfIntangibleAssets`: years=2008 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026, ready=2008 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026, pending=-, decision=SAFE_STANDARD_MAPPING
- MSFT ppe_net sec_companyfacts `us-gaap:PropertyPlantAndEquipmentNet`: years=2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026, ready=2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026, pending=-, decision=SAFE_STANDARD_MAPPING
- MSFT short_term_debt sec_companyfacts `aggregation:us-gaap:LongTermDebtCurrent`: years=2012 2018 2019 2020 2021 2022 2023 2024 2025 2026, ready=-, pending=2012 2018 2019 2020 2021 2022 2023 2024 2025 2026, decision=REVIEW_REQUIRED
- MSFT short_term_debt sec_companyfacts `aggregation:us-gaap:ShortTermBorrowings`: years=2009 2010 2011, ready=-, pending=2009 2010 2011, decision=REVIEW_REQUIRED
- MSFT short_term_debt sec_companyfacts `aggregation:us-gaap:ShortTermBorrowings+us-gaap:LongTermDebtCurrent`: years=2013 2014 2015 2016 2017, ready=2013 2014 2015 2016 2017, pending=-, decision=SAFE_STANDARD_MAPPING
- TSM depreciation_amortization sec_companyfacts `aggregation:ifrs-full:DepreciationExpense+ifrs-full:AmortisationExpense`: years=2015 2016 2017 2018 2019 2020 2021 2022 2023 2024, ready=2015 2016 2017 2018 2019 2020 2021 2022 2023 2024, pending=-, decision=SAFE_STANDARD_MAPPING
- TSM depreciation_amortization sec_filing_xbrl `ifrs-full:DepreciationExpense`: years=2025, ready=-, pending=2025, decision=REVIEW_REQUIRED
- TSM ppe_net sec_companyfacts `ifrs-full:PropertyPlantAndEquipment`: years=2015 2016 2017 2018 2019 2020 2021 2022 2023 2024, ready=2015 2016 2017 2018 2019 2020 2021 2022 2023 2024, pending=-, decision=SAFE_STANDARD_MAPPING
- TSM ppe_net sec_filing_xbrl `ifrs-full:PropertyPlantAndEquipment`: years=2025, ready=2025, pending=-, decision=SAFE_STANDARD_MAPPING
- TSM short_term_debt sec_companyfacts `aggregation:ifrs-full:CurrentPortionOfLongtermBorrowings`: years=2016 2017 2018 2019 2020 2021 2022 2023 2024, ready=-, pending=2016 2017 2018 2019 2020 2021 2022 2023 2024, decision=REVIEW_REQUIRED
- TSM short_term_debt sec_filing_xbrl `ifrs-full:CurrentPortionOfLongtermBorrowings`: years=2025, ready=-, pending=2025, decision=REVIEW_REQUIRED

## 4. Audit Answers
```json
{
  "why_asml_d_and_a_was_not_calculation_ready": "ASML current D&A uses us-gaap:DepreciationDepletionAndAmortization. That standard concept includes depletion in the taxonomy label and is therefore not generically safe for the internal D&A definition without semantic review.",
  "source_present": true,
  "incomplete_d_and_a_component_sum_prevented": true,
  "net_debt_unavailable_reason": "short_term_debt remains REVIEW_REQUIRED when only a current-portion component is available instead of a complete current debt total.",
  "enterprise_value_unavailable_reason": "Enterprise value depends on calculation-ready net_debt; market cap can be ready while EV is EV_REVIEW_REQUIRED.",
  "workflow_statuses_honest": true,
  "core_history_pipeline_proven": true
}
```
