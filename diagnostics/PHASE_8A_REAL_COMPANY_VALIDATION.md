# PHASE_8A_REAL_COMPANY_VALIDATION

## 1. Executive Summary
NO-GO - REAL COMPANY END-TO-END VALIDATION

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
    "FINANCIAL_DATA": "READY",
    "CALCULATION": "READY",
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
    "FINANCIAL_DATA": "READY",
    "CALCULATION": "READY",
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
      "fact_count": 575,
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
    "FINANCIAL_DATA": "READY",
    "CALCULATION": "READY",
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
    "FINANCIAL_DATA": "READY",
    "CALCULATION": "READY",
    "HISTORICAL_ANALYSIS": "READY",
    "BUSINESS_QUALITY": "READY",
    "MARKET_DATA": "READY",
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
    "FINANCIAL_DATA": "READY",
    "CALCULATION": "READY",
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
  "status": "FAIL_LONG_HISTORY_PIPELINE",
  "metrics": {
    "capital_expenditures": {
      "ticker": "ASML",
      "metric": "capital_expenditures",
      "available_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "year_count": 19,
      "earliest_year": 2007,
      "latest_year": 2025,
      "missing_years": "",
      "status": "AVAILABLE"
    },
    "free_cash_flow": {
      "ticker": "ASML",
      "metric": "free_cash_flow",
      "available_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "year_count": 16,
      "earliest_year": 2007,
      "latest_year": 2025,
      "missing_years": "2014 2015 2016",
      "status": "AVAILABLE"
    },
    "net_income": {
      "ticker": "ASML",
      "metric": "net_income",
      "available_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "year_count": 19,
      "earliest_year": 2007,
      "latest_year": 2025,
      "missing_years": "",
      "status": "AVAILABLE"
    },
    "operating_cash_flow": {
      "ticker": "ASML",
      "metric": "operating_cash_flow",
      "available_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "year_count": 16,
      "earliest_year": 2007,
      "latest_year": 2025,
      "missing_years": "2014 2015 2016",
      "status": "AVAILABLE"
    },
    "operating_income": {
      "ticker": "ASML",
      "metric": "operating_income",
      "available_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "year_count": 19,
      "earliest_year": 2007,
      "latest_year": 2025,
      "missing_years": "",
      "status": "AVAILABLE"
    },
    "revenue": {
      "ticker": "ASML",
      "metric": "revenue",
      "available_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "year_count": 19,
      "earliest_year": 2007,
      "latest_year": 2025,
      "missing_years": "",
      "status": "AVAILABLE"
    }
  },
  "missing_required_metrics": [
    "depreciation_amortization"
  ],
  "minimum_core_year_count": 0
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
      "market_snapshot_id": "2d42d9e7523989a86a7e803c99e1a04c204707665bf9f206839f88bb3f93c0e8"
    },
    "TSM": {
      "status": "PASS",
      "valuation_status": "READY_FOR_PREVIEW",
      "market_snapshot_id": "2605f1fb6ed48ddd6630d7b433794d0f84dd72ef94bdb597a15cdcb8bb72a13c"
    },
    "ADBE": {
      "status": "PASS",
      "valuation_status": "READY_FOR_PREVIEW",
      "market_snapshot_id": "05ca1af37eb4b8a512466ded79827b3d0e5d60f4082794b5b0e45f978163b3ed"
    }
  },
  "idempotency_checks": {
    "ASML": {
      "FINANCIAL_DATA": {
        "first_snapshot": "9f737f7f9a7b0750a71ec861fbf9d03e96bee09e0c55e2dcb3a368dce65a6a44",
        "second_snapshot": "9f737f7f9a7b0750a71ec861fbf9d03e96bee09e0c55e2dcb3a368dce65a6a44",
        "idempotent": true
      },
      "CALCULATION": {
        "first_snapshot": "baa32257143ee10fad391d62644cbc8e55c1e54f80cc8b5d4507599c6641971e",
        "second_snapshot": "baa32257143ee10fad391d62644cbc8e55c1e54f80cc8b5d4507599c6641971e",
        "idempotent": true
      },
      "HISTORICAL_ANALYSIS": {
        "first_snapshot": "f2434cd90fc9c7fc925c7840d312acc6db5106d592182bf57583412cf3f38660",
        "second_snapshot": "f2434cd90fc9c7fc925c7840d312acc6db5106d592182bf57583412cf3f38660",
        "idempotent": true
      },
      "BUSINESS_QUALITY": {
        "first_snapshot": "89b7b2921d99ab47f9ce60de34808bf16696183dfb61d5ff838c6cd9167d6705",
        "second_snapshot": "89b7b2921d99ab47f9ce60de34808bf16696183dfb61d5ff838c6cd9167d6705",
        "idempotent": true
      },
      "MARKET_DATA": {
        "first_snapshot": "a1b454144c6f9ed6a93b1b0e7ede0ee0d861d9074b74c590d2161699ba217d97",
        "second_snapshot": "a1b454144c6f9ed6a93b1b0e7ede0ee0d861d9074b74c590d2161699ba217d97",
        "idempotent": true
      },
      "ASSUMPTIONS": {
        "first_snapshot": "4384bf186dac696ff6a95e8f2004ee1213f5540e8e90f97c5cccf2f86a4d7d85",
        "second_snapshot": "4384bf186dac696ff6a95e8f2004ee1213f5540e8e90f97c5cccf2f86a4d7d85",
        "idempotent": true
      },
      "VALUATION": {
        "first_snapshot": "2021db14ccde26667c6b892dcfba4309a6fb6e60c8c222439bf1edfeb0a69d13",
        "second_snapshot": "2021db14ccde26667c6b892dcfba4309a6fb6e60c8c222439bf1edfeb0a69d13",
        "idempotent": true
      }
    },
    "AAPL": {
      "FINANCIAL_DATA": {
        "first_snapshot": "78ef22307d79d306d468f3614dc14e6c48d4cfd4b382d6635bd550280e5de2eb",
        "second_snapshot": "78ef22307d79d306d468f3614dc14e6c48d4cfd4b382d6635bd550280e5de2eb",
        "idempotent": true
      },
      "CALCULATION": {
        "first_snapshot": "f05fb8a3784640e52232d7137f821ecfa566ac333c733220bf5895d77c5013f2",
        "second_snapshot": "f05fb8a3784640e52232d7137f821ecfa566ac333c733220bf5895d77c5013f2",
        "idempotent": true
      },
      "HISTORICAL_ANALYSIS": {
        "first_snapshot": "1e093500b0defb44f115974407493dc59b92ca0572eec9a96d35f9b67538c049",
        "second_snapshot": "1e093500b0defb44f115974407493dc59b92ca0572eec9a96d35f9b67538c049",
        "idempotent": true
      },
      "BUSINESS_QUALITY": {
        "first_snapshot": "05dc45c235bcbf6c360e0ecb9246423834ba0199a23484ff9c7c24eed2bc0018",
        "second_snapshot": "05dc45c235bcbf6c360e0ecb9246423834ba0199a23484ff9c7c24eed2bc0018",
        "idempotent": true
      },
      "MARKET_DATA": {
        "first_snapshot": "7c5a30a1861cb6de02deb3fc21b0320553cdaf66f48173c2ef62f978cd684b98",
        "second_snapshot": "7c5a30a1861cb6de02deb3fc21b0320553cdaf66f48173c2ef62f978cd684b98",
        "idempotent": true
      },
      "ASSUMPTIONS": {
        "first_snapshot": "a0eede132a67149be5415f4ae038bc5c7db02cb517259eb1effbd5b1c4b0ba2e",
        "second_snapshot": "a0eede132a67149be5415f4ae038bc5c7db02cb517259eb1effbd5b1c4b0ba2e",
        "idempotent": true
      },
      "VALUATION": {
        "first_snapshot": "62930b76bdbeaf6c8a6805512a38d389e3552dc48ed1da971a6611efaf84c2fe",
        "second_snapshot": "62930b76bdbeaf6c8a6805512a38d389e3552dc48ed1da971a6611efaf84c2fe",
        "idempotent": true
      }
    },
    "MSFT": {
      "FINANCIAL_DATA": {
        "first_snapshot": "8fe6f0a3423a066cefe97bc1e7f900600be241344a046ed87fefbf721a5d3f17",
        "second_snapshot": "8fe6f0a3423a066cefe97bc1e7f900600be241344a046ed87fefbf721a5d3f17",
        "idempotent": true
      },
      "CALCULATION": {
        "first_snapshot": "2363495977db937e476c8ff91f33f8c9c7c9766aaed5325b89c975a7c73010cf",
        "second_snapshot": "2363495977db937e476c8ff91f33f8c9c7c9766aaed5325b89c975a7c73010cf",
        "idempotent": true
      },
      "HISTORICAL_ANALYSIS": {
        "first_snapshot": "25d54bb398ba381f8e12f9819fa8cdffdbe8cf4e5b9160ebf861e8c0ba4f3332",
        "second_snapshot": "25d54bb398ba381f8e12f9819fa8cdffdbe8cf4e5b9160ebf861e8c0ba4f3332",
        "idempotent": true
      },
      "BUSINESS_QUALITY": {
        "first_snapshot": "0a77d0637fa6ea3cf1cba6323bfbec9a4494a149646ff761e2fc6b92afe84090",
        "second_snapshot": "0a77d0637fa6ea3cf1cba6323bfbec9a4494a149646ff761e2fc6b92afe84090",
        "idempotent": true
      },
      "MARKET_DATA": {
        "first_snapshot": "4c73f09045e969b0fc38a01161131b75a4281b9eff2a87498e6ff75d51ad4819",
        "second_snapshot": "4c73f09045e969b0fc38a01161131b75a4281b9eff2a87498e6ff75d51ad4819",
        "idempotent": true
      },
      "ASSUMPTIONS": {
        "first_snapshot": "0d9f250c12599b67ff0454bef10cda54b46746ac6e7af5873b442051d7ac42c9",
        "second_snapshot": "0d9f250c12599b67ff0454bef10cda54b46746ac6e7af5873b442051d7ac42c9",
        "idempotent": true
      },
      "VALUATION": {
        "first_snapshot": "acabe9d8812a30d7769f9618891bcb8c8dd7db5bd6b583d311dd686b05b219c6",
        "second_snapshot": "acabe9d8812a30d7769f9618891bcb8c8dd7db5bd6b583d311dd686b05b219c6",
        "idempotent": true
      }
    },
    "TSM": {
      "FINANCIAL_DATA": {
        "first_snapshot": "41feacaf09174be50580fc6af367d833133ae6ad237698cbce91d6911355c583",
        "second_snapshot": "41feacaf09174be50580fc6af367d833133ae6ad237698cbce91d6911355c583",
        "idempotent": true
      },
      "CALCULATION": {
        "first_snapshot": "995836861697d3e3024d1039bcd757f5dee6781b3076c56a2f4cff196a4e6991",
        "second_snapshot": "995836861697d3e3024d1039bcd757f5dee6781b3076c56a2f4cff196a4e6991",
        "idempotent": true
      },
      "HISTORICAL_ANALYSIS": {
        "first_snapshot": "e9599e2118735c7ed2e2923456d92ec4665f9a133c8bb82ed68d45d8a969aa65",
        "second_snapshot": "e9599e2118735c7ed2e2923456d92ec4665f9a133c8bb82ed68d45d8a969aa65",
        "idempotent": true
      },
      "BUSINESS_QUALITY": {
        "first_snapshot": "6b3306071837d91967d8d9e6a1f9bf8003438fbab23e62cc70278e49c9a9db96",
        "second_snapshot": "6b3306071837d91967d8d9e6a1f9bf8003438fbab23e62cc70278e49c9a9db96",
        "idempotent": true
      },
      "MARKET_DATA": {
        "first_snapshot": "efa22465b98c08d62f207dbb88ff60e40c99bbd144b46fabe43ba42b541b8238",
        "second_snapshot": "efa22465b98c08d62f207dbb88ff60e40c99bbd144b46fabe43ba42b541b8238",
        "idempotent": true
      },
      "ASSUMPTIONS": {
        "first_snapshot": "364029d9cba8150d56e4aca28dac3f6d2009ac573d6a15c97b841c5caaec6887",
        "second_snapshot": "364029d9cba8150d56e4aca28dac3f6d2009ac573d6a15c97b841c5caaec6887",
        "idempotent": true
      },
      "VALUATION": {
        "first_snapshot": "a0117adc23271448260bbb69d73d46fe284ed4b293e76143a3af7fc44451dc2d",
        "second_snapshot": "a0117adc23271448260bbb69d73d46fe284ed4b293e76143a3af7fc44451dc2d",
        "idempotent": true
      }
    },
    "ADBE": {
      "FINANCIAL_DATA": {
        "first_snapshot": "368d2f93959a2d1944a35319cdfac3af99afcd8d021ce35a26e986a23deaf0a4",
        "second_snapshot": "368d2f93959a2d1944a35319cdfac3af99afcd8d021ce35a26e986a23deaf0a4",
        "idempotent": true
      },
      "CALCULATION": {
        "first_snapshot": "8879451d827b1d5d9ec3ae1eed25c8478527240984ddc62db7772dc88b1fb781",
        "second_snapshot": "8879451d827b1d5d9ec3ae1eed25c8478527240984ddc62db7772dc88b1fb781",
        "idempotent": true
      },
      "HISTORICAL_ANALYSIS": {
        "first_snapshot": "fbc03eab5f2bd2f80253fdc1f4481b2400cba19de44d6c1ec38775b1990299a2",
        "second_snapshot": "fbc03eab5f2bd2f80253fdc1f4481b2400cba19de44d6c1ec38775b1990299a2",
        "idempotent": true
      },
      "BUSINESS_QUALITY": {
        "first_snapshot": "f8409fe379d61d74c17c1fc50552f06a517524049a652475bce823cc96b6ad07",
        "second_snapshot": "f8409fe379d61d74c17c1fc50552f06a517524049a652475bce823cc96b6ad07",
        "idempotent": true
      },
      "MARKET_DATA": {
        "first_snapshot": "2d2ac7ebb5a5355bceb8ccd9eaa811d9fe7d9cbd076e27df3209d72c2df8d2b5",
        "second_snapshot": "2d2ac7ebb5a5355bceb8ccd9eaa811d9fe7d9cbd076e27df3209d72c2df8d2b5",
        "idempotent": true
      },
      "ASSUMPTIONS": {
        "first_snapshot": "09db5cf0b0f54dc7be32eacecbbaa897b02e7f29a3393af3c87580e247ee699f",
        "second_snapshot": "09db5cf0b0f54dc7be32eacecbbaa897b02e7f29a3393af3c87580e247ee699f",
        "idempotent": true
      },
      "VALUATION": {
        "first_snapshot": "30f4b8a734a7d160a7c4b53d1c02950c2f735b0613556957be718be2602c4d03",
        "second_snapshot": "30f4b8a734a7d160a7c4b53d1c02950c2f735b0613556957be718be2602c4d03",
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
- ASML LONG_HISTORY: required core metric history below 5Y (depreciation_amortization)

## 20. GO / NO-GO
NO-GO - REAL COMPANY END-TO-END VALIDATION
