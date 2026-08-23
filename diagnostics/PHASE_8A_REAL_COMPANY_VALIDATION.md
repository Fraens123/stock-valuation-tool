# PHASE_8A_REAL_COMPANY_VALIDATION

## 1. Executive Summary
GO - REAL COMPANY END-TO-END VALIDATION PASSED

## 2. Environment Preflight
```json
{
  "configured": {
    "SEC_USER_AGENT": true,
    "ALPHA_VANTAGE_API_KEY": true,
    "STOOQ_QUOTE": true,
    "FRANKFURTER_FX": true,
    "OPEN_ER_FX": true
  },
  "dotenv_path_found": true,
  "SEC_USER_AGENT_SOURCE": "DOTENV",
  "ALPHA_VANTAGE_API_KEY_SOURCE": "DOTENV",
  "runtime_environment": {
    "repo_root": "C:\\Users\\Fraens\\Documents\\Fraens\\Finanzen\\Portfolio-Aufbau\\Aktien Analyse Tool\\stock-valuation-tool",
    "current_working_directory": "C:\\Users\\Fraens\\Documents\\Fraens\\Finanzen\\Portfolio-Aufbau\\Aktien Analyse Tool\\stock-valuation-tool",
    "expected_dotenv_path": "C:\\Users\\Fraens\\Documents\\Fraens\\Finanzen\\Portfolio-Aufbau\\Aktien Analyse Tool\\stock-valuation-tool\\.env",
    "dotenv_path_found": true,
    "dotenv_candidates": {
      "C:\\Users\\Fraens\\Documents\\Fraens\\Finanzen\\Portfolio-Aufbau\\Aktien Analyse Tool\\stock-valuation-tool\\.env": {
        "exists": false,
        "keys": {
          "SEC_USER_AGENT": {
            "present": false,
            "non_empty": false
          },
          "ALPHA_VANTAGE_API_KEY": {
            "present": false,
            "non_empty": false
          }
        }
      },
      "C:\\Users\\Fraens\\Documents\\Fraens\\Finanzen\\Portfolio-Aufbau\\Aktien Analyse Tool\\.env": {
        "exists": true,
        "keys": {
          "SEC_USER_AGENT": {
            "present": true,
            "non_empty": true
          },
          "ALPHA_VANTAGE_API_KEY": {
            "present": true,
            "non_empty": true
          }
        }
      }
    },
    "sources": {
      "SEC_USER_AGENT": "DOTENV",
      "ALPHA_VANTAGE_API_KEY": "DOTENV"
    },
    "process_after_load": {
      "SEC_USER_AGENT": {
        "configured": true,
        "non_empty": true
      },
      "ALPHA_VANTAGE_API_KEY": {
        "configured": true,
        "non_empty": true
      }
    }
  },
  "environment_blockers": []
}
```

## 3. Validation DB
`diagnostics\runtime\phase8a_validation.sqlite`

## 4. Production Code Path
Diagnostics CSV input: `False`

## 5. ASML
```json
{
  "analysis_id": 1,
  "analysis_as_of_date": "2026-08-23",
  "financial_source": "SEC",
  "financial_attempts": [
    {
      "source": "SEC Company Facts",
      "status": "selected",
      "fact_count": 414,
      "identifier": "0000937966",
      "message": "Offizielle aggregierte SEC-XBRL-Daten."
    },
    {
      "source": "SEC Original-Filing",
      "status": "checked_no_standard_fill",
      "fact_count": 0,
      "identifier": "0000937966",
      "message": "Originalfilings geprüft; keine zusätzliche sichere Standard-XBRL-Zuordnung gefunden. 10 Feld/Jahr-Kombination(en) benötigen noch eine Company-Extension-/Textprüfung."
    },
    {
      "source": "SEC Extension-Mapping",
      "status": "checked_no_candidate",
      "fact_count": 0,
      "identifier": "0000937966",
      "message": "Keine ausreichend plausiblen firmeneigenen XBRL-Kandidaten gefunden. 10 Feld/Jahr-Kombination(en) bleiben weiterhin offen."
    }
  ],
  "stage_statuses": {
    "FINANCIAL_DATA": "REVIEW_REQUIRED",
    "CALCULATION": "REVIEW_REQUIRED",
    "HISTORICAL_ANALYSIS": "READY",
    "BUSINESS_QUALITY": "READY",
    "MARKET_DATA": "REVIEW_REQUIRED",
    "ASSUMPTIONS": "REVIEW_REQUIRED",
    "VALUATION": "READY_FOR_PREVIEW"
  },
  "history_years": [
    2006,
    2007,
    2008,
    2009,
    2010,
    2011,
    2012,
    2013,
    2014,
    2015,
    2016,
    2017,
    2018,
    2019,
    2020,
    2021,
    2022,
    2023,
    2024,
    2025
  ],
  "listing": {
    "ticker": "ASML",
    "exchange": "Euronext Amsterdam",
    "security_type": "ordinary_share",
    "trading_currency": "EUR",
    "financial_currency": "EUR",
    "adr_ratio": null,
    "underlying_share_ratio": null,
    "share_basis": "ORDINARY_SHARES"
  }
}
```
## 6. AAPL
```json
{
  "analysis_id": 2,
  "analysis_as_of_date": "2026-08-23",
  "financial_source": "SEC",
  "financial_attempts": [
    {
      "source": "SEC Company Facts",
      "status": "selected",
      "fact_count": 536,
      "identifier": "0000320193",
      "message": "Offizielle aggregierte SEC-XBRL-Daten."
    },
    {
      "source": "SEC Original-Filing",
      "status": "checked_no_standard_fill",
      "fact_count": 0,
      "identifier": "0000320193",
      "message": "Originalfilings geprüft; keine zusätzliche sichere Standard-XBRL-Zuordnung gefunden. 20 Feld/Jahr-Kombination(en) benötigen noch eine Company-Extension-/Textprüfung."
    },
    {
      "source": "SEC Extension-Mapping",
      "status": "candidates_found",
      "fact_count": 2,
      "identifier": "0000320193",
      "message": "2 firmeneigene XBRL-Kandidat(en) aus 10 Filing-Prüfung(en) gefunden. Sie bleiben bis zum semantischen PASS blockiert. 18 Feld/Jahr-Kombination(en) bleiben weiterhin offen."
    }
  ],
  "stage_statuses": {
    "FINANCIAL_DATA": "REVIEW_REQUIRED",
    "CALCULATION": "REVIEW_REQUIRED",
    "HISTORICAL_ANALYSIS": "READY",
    "BUSINESS_QUALITY": "READY",
    "MARKET_DATA": "REVIEW_REQUIRED",
    "ASSUMPTIONS": "REVIEW_REQUIRED",
    "VALUATION": "READY_FOR_PREVIEW"
  },
  "history_years": [
    2006,
    2007,
    2008,
    2009,
    2010,
    2011,
    2012,
    2013,
    2014,
    2015,
    2016,
    2017,
    2018,
    2019,
    2020,
    2021,
    2022,
    2023,
    2024,
    2025
  ],
  "listing": {
    "ticker": "AAPL",
    "exchange": "NASDAQ",
    "security_type": "ordinary_share",
    "trading_currency": "USD",
    "financial_currency": "USD",
    "adr_ratio": null,
    "underlying_share_ratio": null,
    "share_basis": "ORDINARY_SHARES"
  }
}
```
## 7. MSFT
```json
{
  "analysis_id": 3,
  "analysis_as_of_date": "2026-08-23",
  "financial_source": "SEC",
  "financial_attempts": [
    {
      "source": "SEC Company Facts",
      "status": "selected",
      "fact_count": 574,
      "identifier": "0000789019",
      "message": "Offizielle aggregierte SEC-XBRL-Daten."
    },
    {
      "source": "SEC Original-Filing",
      "status": "checked_no_standard_fill",
      "fact_count": 0,
      "identifier": "0000789019",
      "message": "Originalfilings geprüft; keine zusätzliche sichere Standard-XBRL-Zuordnung gefunden. 1 Feld/Jahr-Kombination(en) benötigen noch eine Company-Extension-/Textprüfung."
    },
    {
      "source": "SEC Extension-Mapping",
      "status": "checked_no_candidate",
      "fact_count": 0,
      "identifier": "0000789019",
      "message": "Keine ausreichend plausiblen firmeneigenen XBRL-Kandidaten gefunden. 1 Feld/Jahr-Kombination(en) bleiben weiterhin offen."
    }
  ],
  "stage_statuses": {
    "FINANCIAL_DATA": "REVIEW_REQUIRED",
    "CALCULATION": "REVIEW_REQUIRED",
    "HISTORICAL_ANALYSIS": "READY",
    "BUSINESS_QUALITY": "READY",
    "MARKET_DATA": "READY",
    "ASSUMPTIONS": "REVIEW_REQUIRED",
    "VALUATION": "READY_FOR_PREVIEW"
  },
  "history_years": [
    2007,
    2008,
    2009,
    2010,
    2011,
    2012,
    2013,
    2014,
    2015,
    2016,
    2017,
    2018,
    2019,
    2020,
    2021,
    2022,
    2023,
    2024,
    2025,
    2026
  ],
  "listing": {
    "ticker": "MSFT",
    "exchange": "NASDAQ",
    "security_type": "ordinary_share",
    "trading_currency": "USD",
    "financial_currency": "USD",
    "adr_ratio": null,
    "underlying_share_ratio": null,
    "share_basis": "ORDINARY_SHARES"
  }
}
```
## 8. TSM
```json
{
  "analysis_id": 4,
  "analysis_as_of_date": "2026-08-23",
  "financial_source": "SEC",
  "financial_attempts": [
    {
      "source": "SEC Company Facts",
      "status": "selected",
      "fact_count": 219,
      "identifier": "0001046179",
      "message": "Offizielle aggregierte SEC-XBRL-Daten."
    },
    {
      "source": "SEC Original-Filing",
      "status": "supplemented",
      "fact_count": 23,
      "identifier": "0001046179",
      "message": "23 fehlende Standard-XBRL-Fakten aus 4 Originalfiling(s) ergänzt. 13 Feld/Jahr-Kombination(en) benötigen noch eine Company-Extension-/Textprüfung."
    },
    {
      "source": "SEC Extension-Mapping",
      "status": "checked_no_candidate",
      "fact_count": 0,
      "identifier": "0001046179",
      "message": "Keine ausreichend plausiblen firmeneigenen XBRL-Kandidaten gefunden. 13 Feld/Jahr-Kombination(en) bleiben weiterhin offen."
    }
  ],
  "stage_statuses": {
    "FINANCIAL_DATA": "REVIEW_REQUIRED",
    "CALCULATION": "REVIEW_REQUIRED",
    "HISTORICAL_ANALYSIS": "READY",
    "BUSINESS_QUALITY": "READY",
    "MARKET_DATA": "REVIEW_REQUIRED",
    "ASSUMPTIONS": "REVIEW_REQUIRED",
    "VALUATION": "READY_FOR_PREVIEW"
  },
  "history_years": [
    2014,
    2015,
    2016,
    2017,
    2018,
    2019,
    2020,
    2021,
    2022,
    2023,
    2024,
    2025
  ],
  "listing": {
    "ticker": "TSM",
    "exchange": "NYSE",
    "security_type": "ADR",
    "trading_currency": "USD",
    "financial_currency": "TWD",
    "adr_ratio": "1",
    "underlying_share_ratio": "5",
    "share_basis": "ORDINARY_SHARES"
  }
}
```
## 9. ADBE
```json
{
  "analysis_id": 5,
  "analysis_as_of_date": "2026-08-23",
  "financial_source": "SEC",
  "financial_attempts": [
    {
      "source": "SEC Company Facts",
      "status": "selected",
      "fact_count": 538,
      "identifier": "0000796343",
      "message": "Offizielle aggregierte SEC-XBRL-Daten."
    },
    {
      "source": "SEC Original-Filing",
      "status": "checked_no_standard_fill",
      "fact_count": 0,
      "identifier": "0000796343",
      "message": "Originalfilings geprüft; keine zusätzliche sichere Standard-XBRL-Zuordnung gefunden. 5 Feld/Jahr-Kombination(en) benötigen noch eine Company-Extension-/Textprüfung."
    },
    {
      "source": "SEC Extension-Mapping",
      "status": "candidates_found",
      "fact_count": 2,
      "identifier": "0000796343",
      "message": "2 firmeneigene XBRL-Kandidat(en) aus 3 Filing-Prüfung(en) gefunden. Sie bleiben bis zum semantischen PASS blockiert. 3 Feld/Jahr-Kombination(en) bleiben weiterhin offen."
    }
  ],
  "stage_statuses": {
    "FINANCIAL_DATA": "REVIEW_REQUIRED",
    "CALCULATION": "REVIEW_REQUIRED",
    "HISTORICAL_ANALYSIS": "READY",
    "BUSINESS_QUALITY": "READY",
    "MARKET_DATA": "READY",
    "ASSUMPTIONS": "REVIEW_REQUIRED",
    "VALUATION": "READY_FOR_PREVIEW"
  },
  "history_years": [
    2006,
    2007,
    2008,
    2009,
    2010,
    2011,
    2012,
    2013,
    2014,
    2015,
    2016,
    2017,
    2018,
    2019,
    2020,
    2021,
    2022,
    2023,
    2024,
    2025
  ],
  "listing": {
    "ticker": "ADBE",
    "exchange": "NASDAQ",
    "security_type": "ordinary_share",
    "trading_currency": "USD",
    "financial_currency": "USD",
    "adr_ratio": null,
    "underlying_share_ratio": null,
    "share_basis": "ORDINARY_SHARES"
  }
}
```

## 6. ASML Long-History Proof
```json
{
  "status": "LONG_HISTORY_PASS_WITH_REVIEW_GAPS",
  "core_historical_series": {
    "capital_expenditures": {
      "ticker": "ASML",
      "metric": "capital_expenditures",
      "source_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "source_year_count": 19,
      "review_pending_fiscal_years": "",
      "review_pending_year_count": 0,
      "calculation_ready_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "calculation_ready_year_count": 19,
      "missing_source_years": "",
      "earliest_source_year": 2007,
      "latest_source_year": 2025,
      "coverage_status": "CALCULATION_READY_10Y"
    },
    "free_cash_flow": {
      "ticker": "ASML",
      "metric": "free_cash_flow",
      "source_fiscal_years": "",
      "source_year_count": 0,
      "review_pending_fiscal_years": "",
      "review_pending_year_count": 0,
      "calculation_ready_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "calculation_ready_year_count": 16,
      "missing_source_years": "",
      "earliest_source_year": "",
      "latest_source_year": "",
      "coverage_status": "DERIVED_CALCULATION_READY_10Y"
    },
    "net_income": {
      "ticker": "ASML",
      "metric": "net_income",
      "source_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "source_year_count": 19,
      "review_pending_fiscal_years": "",
      "review_pending_year_count": 0,
      "calculation_ready_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "calculation_ready_year_count": 19,
      "missing_source_years": "",
      "earliest_source_year": 2007,
      "latest_source_year": 2025,
      "coverage_status": "CALCULATION_READY_10Y"
    },
    "operating_cash_flow": {
      "ticker": "ASML",
      "metric": "operating_cash_flow",
      "source_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "source_year_count": 16,
      "review_pending_fiscal_years": "",
      "review_pending_year_count": 0,
      "calculation_ready_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "calculation_ready_year_count": 16,
      "missing_source_years": "2014 2015 2016",
      "earliest_source_year": 2007,
      "latest_source_year": 2025,
      "coverage_status": "CALCULATION_READY_10Y"
    },
    "operating_income": {
      "ticker": "ASML",
      "metric": "operating_income",
      "source_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "source_year_count": 19,
      "review_pending_fiscal_years": "",
      "review_pending_year_count": 0,
      "calculation_ready_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "calculation_ready_year_count": 19,
      "missing_source_years": "",
      "earliest_source_year": 2007,
      "latest_source_year": 2025,
      "coverage_status": "CALCULATION_READY_10Y"
    },
    "revenue": {
      "ticker": "ASML",
      "metric": "revenue",
      "source_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "source_year_count": 19,
      "review_pending_fiscal_years": "",
      "review_pending_year_count": 0,
      "calculation_ready_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "calculation_ready_year_count": 19,
      "missing_source_years": "",
      "earliest_source_year": 2007,
      "latest_source_year": 2025,
      "coverage_status": "CALCULATION_READY_10Y"
    }
  },
  "supporting_derived_history": {
    "depreciation_amortization": {
      "ticker": "ASML",
      "metric": "depreciation_amortization",
      "source_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "source_year_count": 19,
      "review_pending_fiscal_years": "2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "review_pending_year_count": 14,
      "calculation_ready_fiscal_years": "2007 2008 2009 2010 2011",
      "calculation_ready_year_count": 5,
      "missing_source_years": "",
      "earliest_source_year": 2007,
      "latest_source_year": 2025,
      "coverage_status": "CALCULATION_READY_5Y"
    },
    "ebitda": {
      "ticker": "ASML",
      "metric": "ebitda",
      "source_fiscal_years": "",
      "source_year_count": 0,
      "review_pending_fiscal_years": "2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "review_pending_year_count": 14,
      "calculation_ready_fiscal_years": "2007 2008 2009 2010 2011",
      "calculation_ready_year_count": 5,
      "missing_source_years": "",
      "earliest_source_year": "",
      "latest_source_year": "",
      "coverage_status": "DERIVED_CALCULATION_READY_5Y"
    },
    "net_debt": {
      "ticker": "ASML",
      "metric": "net_debt",
      "source_fiscal_years": "",
      "source_year_count": 0,
      "review_pending_fiscal_years": "2010 2011 2012 2013 2014 2018 2019 2020 2021 2022 2023 2024 2025",
      "review_pending_year_count": 13,
      "calculation_ready_fiscal_years": "",
      "calculation_ready_year_count": 0,
      "missing_source_years": "",
      "earliest_source_year": "",
      "latest_source_year": "",
      "coverage_status": "DERIVED_SEMANTIC_REVIEW_REQUIRED"
    },
    "short_term_debt": {
      "ticker": "ASML",
      "metric": "short_term_debt",
      "source_fiscal_years": "2010 2011 2012 2013 2014 2018 2019 2020 2021 2022 2023 2024 2025",
      "source_year_count": 13,
      "review_pending_fiscal_years": "2010 2011 2012 2013 2014 2018 2019 2020 2021 2022 2023 2024 2025",
      "review_pending_year_count": 13,
      "calculation_ready_fiscal_years": "",
      "calculation_ready_year_count": 0,
      "missing_source_years": "2015 2016 2017",
      "earliest_source_year": 2010,
      "latest_source_year": 2025,
      "coverage_status": "SEMANTIC_REVIEW_REQUIRED"
    }
  },
  "missing_required_metrics": [],
  "minimum_core_year_count": 16
}
```

## 11. Financial Data Results
Siehe `diagnostics/phase8a_company_results.csv`.

## 12. Calculation Results
Siehe `diagnostics/phase8a_stage_results.csv`.

## 13. Historical Analysis Results
Siehe `diagnostics/phase8a_history_coverage.csv`.

## 14. Business Quality Results
Siehe Company- und Stage-CSV.

## 15. Market Data Results
Siehe Company- und Stage-CSV.

## 16. Assumption Results
Review Required ist fuer echte Unternehmen erlaubt und kein Engine-Fehler.

## 17. Valuation Preview Results
Siehe `bear_fair_value`, `base_fair_value`, `bull_fair_value` in Company-CSV.

## 18. Snapshot / Reopen / Immutability
```json
{
  "reopen_checks": {
    "ASML": {
      "status": "PASS",
      "valuation_status": "READY_FOR_PREVIEW",
      "market_snapshot_id": "bdb9bf63e6dfdee6ebf8c83dfe761b02176b64a3d059a1ff0627fb0e6cfb7150"
    },
    "AAPL": {
      "status": "PASS",
      "valuation_status": "READY_FOR_PREVIEW",
      "market_snapshot_id": "5939e428bfe11bf9ed8a20e3fb811f3c1aa6773d98418b740eecbf4cd6143eb1"
    },
    "MSFT": {
      "status": "PASS",
      "valuation_status": "READY_FOR_PREVIEW",
      "market_snapshot_id": "f566ff7c6b34dc452800ea113d1e69e350b9db5e870df6ca09fa014195c93f8b"
    },
    "TSM": {
      "status": "PASS",
      "valuation_status": "READY_FOR_PREVIEW",
      "market_snapshot_id": "2605f1fb6ed48ddd6630d7b433794d0f84dd72ef94bdb597a15cdcb8bb72a13c"
    },
    "ADBE": {
      "status": "PASS",
      "valuation_status": "READY_FOR_PREVIEW",
      "market_snapshot_id": "ed469c845e391a8c8bab0f3edfda2c4b83d458a9c25fe7a257b6ecac162857fa"
    }
  },
  "idempotency_checks": {
    "ASML": {
      "FINANCIAL_DATA": {
        "first_snapshot": "ef89521c367a81e21ca65af6e43117a18aacf1d3bc7c447c9b2b0093c2821747",
        "second_snapshot": "ef89521c367a81e21ca65af6e43117a18aacf1d3bc7c447c9b2b0093c2821747",
        "idempotent": true
      },
      "CALCULATION": {
        "first_snapshot": "e466887b20ce97c25bfc17ca0c15c58efbd6cd024ef68123999e929d92192932",
        "second_snapshot": "e466887b20ce97c25bfc17ca0c15c58efbd6cd024ef68123999e929d92192932",
        "idempotent": true
      },
      "HISTORICAL_ANALYSIS": {
        "first_snapshot": "939cc786668a184105c5bf14f9888f822558ba62326369cfe12001e834e64c02",
        "second_snapshot": "939cc786668a184105c5bf14f9888f822558ba62326369cfe12001e834e64c02",
        "idempotent": true
      },
      "BUSINESS_QUALITY": {
        "first_snapshot": "79dddb1abd20f2f73c28fe3638d1af00fa6c0331deeb69fcf66215863ed172b2",
        "second_snapshot": "79dddb1abd20f2f73c28fe3638d1af00fa6c0331deeb69fcf66215863ed172b2",
        "idempotent": true
      },
      "MARKET_DATA": {
        "first_snapshot": "c13018b710c409e8d718852178cc0fe7f55fa2894218d20c901f8174364db71c",
        "second_snapshot": "c13018b710c409e8d718852178cc0fe7f55fa2894218d20c901f8174364db71c",
        "idempotent": true
      },
      "ASSUMPTIONS": {
        "first_snapshot": "3ac8e986c4d92df0574ba2c7c57ca1083aef9cf723a8eda7f6ff20d5e943642f",
        "second_snapshot": "3ac8e986c4d92df0574ba2c7c57ca1083aef9cf723a8eda7f6ff20d5e943642f",
        "idempotent": true
      },
      "VALUATION": {
        "first_snapshot": "70e9a315f2eedbb4e082015b5576cf89672bdb7485c97e4685f2f620550aa5e9",
        "second_snapshot": "70e9a315f2eedbb4e082015b5576cf89672bdb7485c97e4685f2f620550aa5e9",
        "idempotent": true
      }
    },
    "AAPL": {
      "FINANCIAL_DATA": {
        "first_snapshot": "e8daca2b16efbf6b99971a4f148518227553331fb09116f87f056339b75e743d",
        "second_snapshot": "e8daca2b16efbf6b99971a4f148518227553331fb09116f87f056339b75e743d",
        "idempotent": true
      },
      "CALCULATION": {
        "first_snapshot": "e6c06ff64e3689db8316c4891262b81abae38f4eccdd2d0f8c9c42d33f2d09e1",
        "second_snapshot": "e6c06ff64e3689db8316c4891262b81abae38f4eccdd2d0f8c9c42d33f2d09e1",
        "idempotent": true
      },
      "HISTORICAL_ANALYSIS": {
        "first_snapshot": "6077be787ebfd4a4f322b649190064e11ebbb3b767b0b2dc79430c987d2558e5",
        "second_snapshot": "6077be787ebfd4a4f322b649190064e11ebbb3b767b0b2dc79430c987d2558e5",
        "idempotent": true
      },
      "BUSINESS_QUALITY": {
        "first_snapshot": "253f8271c9415788f0c3e739cb0137d7bd45a1043eb48a743108a216453ec792",
        "second_snapshot": "253f8271c9415788f0c3e739cb0137d7bd45a1043eb48a743108a216453ec792",
        "idempotent": true
      },
      "MARKET_DATA": {
        "first_snapshot": "941560e71e788df68ad956497c4515546b096f22bca99f367e092bcc00676b73",
        "second_snapshot": "941560e71e788df68ad956497c4515546b096f22bca99f367e092bcc00676b73",
        "idempotent": true
      },
      "ASSUMPTIONS": {
        "first_snapshot": "9d464eed841c38a91e015ca4f999eadf12c3791c27d804492b3e6372920a1dd2",
        "second_snapshot": "9d464eed841c38a91e015ca4f999eadf12c3791c27d804492b3e6372920a1dd2",
        "idempotent": true
      },
      "VALUATION": {
        "first_snapshot": "3526d5cd2a3f290b28241584174595f27e1a5360c9276013e7962c225078698b",
        "second_snapshot": "3526d5cd2a3f290b28241584174595f27e1a5360c9276013e7962c225078698b",
        "idempotent": true
      }
    },
    "MSFT": {
      "FINANCIAL_DATA": {
        "first_snapshot": "b6dd70f085be245d39f5d2b459fb4939bfb53becc87de8d6380b6305d7ceb45a",
        "second_snapshot": "b6dd70f085be245d39f5d2b459fb4939bfb53becc87de8d6380b6305d7ceb45a",
        "idempotent": true
      },
      "CALCULATION": {
        "first_snapshot": "3b50c7a4bce86fb30361d072be3b016842043910a3e507de40d626698103123f",
        "second_snapshot": "3b50c7a4bce86fb30361d072be3b016842043910a3e507de40d626698103123f",
        "idempotent": true
      },
      "HISTORICAL_ANALYSIS": {
        "first_snapshot": "dcbe12dcd1a6ef1c72b6cf6c5a3b30d6da77e40ed920c234d4b334e193852a59",
        "second_snapshot": "dcbe12dcd1a6ef1c72b6cf6c5a3b30d6da77e40ed920c234d4b334e193852a59",
        "idempotent": true
      },
      "BUSINESS_QUALITY": {
        "first_snapshot": "f68bda79a27249dbe7b15094bc02156b8239411a03e9778d64cdebab61436999",
        "second_snapshot": "f68bda79a27249dbe7b15094bc02156b8239411a03e9778d64cdebab61436999",
        "idempotent": true
      },
      "MARKET_DATA": {
        "first_snapshot": "47534d873bc3a4ad68821d3a7456a0bd12910f54da180ff24a7c881fc90b9ce5",
        "second_snapshot": "47534d873bc3a4ad68821d3a7456a0bd12910f54da180ff24a7c881fc90b9ce5",
        "idempotent": true
      },
      "ASSUMPTIONS": {
        "first_snapshot": "545efdad1acf9928d5979fc6afe96f0f5f082b0da76fd18b93e251cf19a3f7c8",
        "second_snapshot": "545efdad1acf9928d5979fc6afe96f0f5f082b0da76fd18b93e251cf19a3f7c8",
        "idempotent": true
      },
      "VALUATION": {
        "first_snapshot": "f552db9345fcbd5ccfd6e4ee761938fcddb0dd04115ca5e2a6bb0ebe1c7b9cc3",
        "second_snapshot": "f552db9345fcbd5ccfd6e4ee761938fcddb0dd04115ca5e2a6bb0ebe1c7b9cc3",
        "idempotent": true
      }
    },
    "TSM": {
      "FINANCIAL_DATA": {
        "first_snapshot": "4d951ef34da01110ba67da77cdc31558b5f6d32545dbaab5f5a925ea1a6ec11e",
        "second_snapshot": "4d951ef34da01110ba67da77cdc31558b5f6d32545dbaab5f5a925ea1a6ec11e",
        "idempotent": true
      },
      "CALCULATION": {
        "first_snapshot": "723c6cde053a272b9ffddf706d8bfbc0033748509f6771355a367d03cb0bf1d2",
        "second_snapshot": "723c6cde053a272b9ffddf706d8bfbc0033748509f6771355a367d03cb0bf1d2",
        "idempotent": true
      },
      "HISTORICAL_ANALYSIS": {
        "first_snapshot": "6143aa50000505b1e146976b929a789347ca3ce1c4c840643fda6ba672f5c3b7",
        "second_snapshot": "6143aa50000505b1e146976b929a789347ca3ce1c4c840643fda6ba672f5c3b7",
        "idempotent": true
      },
      "BUSINESS_QUALITY": {
        "first_snapshot": "db3a8177882d49daec37134ca3e0c47356a44097b2f7f5828a08ce715d9d5e60",
        "second_snapshot": "db3a8177882d49daec37134ca3e0c47356a44097b2f7f5828a08ce715d9d5e60",
        "idempotent": true
      },
      "MARKET_DATA": {
        "first_snapshot": "2642032b21519f4ccf10c5a16e2b0d6e4b906637e6f8983d77973f3808c52e0a",
        "second_snapshot": "2642032b21519f4ccf10c5a16e2b0d6e4b906637e6f8983d77973f3808c52e0a",
        "idempotent": true
      },
      "ASSUMPTIONS": {
        "first_snapshot": "6df88b9e229b462a06468610fdedb59ff31da3729b700450f1d08423e7523d69",
        "second_snapshot": "6df88b9e229b462a06468610fdedb59ff31da3729b700450f1d08423e7523d69",
        "idempotent": true
      },
      "VALUATION": {
        "first_snapshot": "a34f14c6079e1c832506dd33d28b785fa232fdbac41d11a38b4806c76028d9d7",
        "second_snapshot": "a34f14c6079e1c832506dd33d28b785fa232fdbac41d11a38b4806c76028d9d7",
        "idempotent": true
      }
    },
    "ADBE": {
      "FINANCIAL_DATA": {
        "first_snapshot": "08f779989b24bbdc6d608bf62a0b1ebdf6a86be49711b682318331b87712e986",
        "second_snapshot": "08f779989b24bbdc6d608bf62a0b1ebdf6a86be49711b682318331b87712e986",
        "idempotent": true
      },
      "CALCULATION": {
        "first_snapshot": "e533d99e359499939e694e0dc58a69308231a74a367c34dcc62f600811a3641b",
        "second_snapshot": "e533d99e359499939e694e0dc58a69308231a74a367c34dcc62f600811a3641b",
        "idempotent": true
      },
      "HISTORICAL_ANALYSIS": {
        "first_snapshot": "0ced5102fd8129829a90057d69fcf647ab59f00a2eacdc062646d4913407d9ef",
        "second_snapshot": "0ced5102fd8129829a90057d69fcf647ab59f00a2eacdc062646d4913407d9ef",
        "idempotent": true
      },
      "BUSINESS_QUALITY": {
        "first_snapshot": "a5a97a4aa0a824ab8244be80af8461985c2ba5b4989b3d146b2b04525dbddcd9",
        "second_snapshot": "a5a97a4aa0a824ab8244be80af8461985c2ba5b4989b3d146b2b04525dbddcd9",
        "idempotent": true
      },
      "MARKET_DATA": {
        "first_snapshot": "84d521959a3209797b60987071da7a18a21c14cca29982208119af4802490c02",
        "second_snapshot": "84d521959a3209797b60987071da7a18a21c14cca29982208119af4802490c02",
        "idempotent": true
      },
      "ASSUMPTIONS": {
        "first_snapshot": "81e721a604920d3f96d4f220b34d6376251621c55bfd731abeed4a4a677498db",
        "second_snapshot": "81e721a604920d3f96d4f220b34d6376251621c55bfd731abeed4a4a677498db",
        "idempotent": true
      },
      "VALUATION": {
        "first_snapshot": "843615caad76ed9e10773d31640fc6477e5bf7dd01ec2af71aced1da9443b9d8",
        "second_snapshot": "843615caad76ed9e10773d31640fc6477e5bf7dd01ec2af71aced1da9443b9d8",
        "idempotent": true
      }
    }
  }
}
```

## 19. Test Suite
Normaler Testlauf bleibt separat: `pytest -q`.

## Provider Failures
- keine

## Engine Blockers
- keine

## 20. GO / NO-GO
GO - REAL COMPANY END-TO-END VALIDATION PASSED
