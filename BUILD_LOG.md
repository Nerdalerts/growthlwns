# GrowthLens Copilot - Build Log

This log tracks every discrepancy, bug, failure mode, and resolution encountered during the development of GrowthLens Copilot.

---

## Initial Setup & Baseline
- **Date:** 2026-10-22
- **Action:** Initialized repository with base GrowthLens code and real Olist dataset files. Verified environment dependencies: Python 3.13, DuckDB 2.0.0, sqlglot 30.24.0, Anthropic SDK 2.0.0, Streamlit 1.56.0, pandas 2.3.3, scipy 1.16.2, pytest 9.0.3.

## Milestone 0: Repo Audit
- **Date:** 2026-10-22
- **Audit Findings:**
  1. **Metric Discrepancies:**
     - In `data/loader.py`, GMV is calculated as `sum(price)` across `delivered` orders.
     - In `data/olist_loader.py`, revenue is calculated as `price + freight_value`.
     - In `data/loader.py`, DAU and MAU are synthetic heuristics (`orders * 8` and `dau * 7.2`) because Olist is an order database without web session logs. Questions about DAU/MAU must be marked out-of-scope/refused in SQL Q&A since clickstream data does not exist in Olist.
  2. **Data Layer:**
     - 8 core CSVs identified in `data/olist_raw/`. All row counts verified: customers (99,441), items (112,650), payments (103,886), reviews (99,224), orders (99,441), products (32,951), sellers (3,095), category translations (71).
  3. **Risks Addressed:**
     - Join fan-out between `order_items` and `order_payments`.
     - Forced `order_status = 'delivered'` filter for standard metrics.
     - ISO timestamp string parsing in DuckDB.

## Milestone 1: Data Layer
- **Date:** 2026-10-22
- **Completed:** Implemented `copilot/data/build.py` and `tests/test_data_build.py`. Loaded 8 Olist tables into DuckDB at `data/olist.duckdb`.
- **What Broke #1 (Encoding):** `UnicodeEncodeError: 'charmap' codec can't encode character '\u2713'`.
  - *How Found:* Running `python -m copilot.data.build` in Windows PowerShell (default cp1252 code page).
  - *How Fixed:* Replaced unicode checkmarks with ASCII `[OK]` and `[MISMATCH]`.
- **What Broke #2 (CSV Line Counting):** `order_reviews` showed 99,224 rows in DuckDB vs 104,719 rows in line-by-line file read.
  - *How Found:* `build_database` row-count validation reported a mismatch for `order_reviews`.
  - *How Fixed:* The raw CSV contains embedded newline characters `\n` inside quoted review comments (`review_comment_message`). Switched row-counter to standard `csv.reader()`, which accurately parses multiline quoted records and verified exactly 99,224 rows.
- **Tests Passed:** All 3 unit tests in `tests/test_data_build.py` passed (testing data dir location, schema data types, row counts, and idempotency).

## Milestone 2: Metrics Semantic Layer
- **Date:** 2026-10-22
- **Completed:** Created `metrics.yaml` defining GMV, order_count, AOV, delivered_order_rate, avg_review_score, repeat_customer_rate, and on_time_delivery_rate with descriptions, SQL, grain, filters, and pitfalls. Implemented `copilot/metrics.py` and `tests/test_metrics.py`.
- **Discrepancy Audit & Resolutions:**
  1. *GMV Calculation:* GrowthLens's `data/loader.py` computes `revenue = sum(price)` while `data/olist_loader.py` computes `price + freight_value`. We standardized GMV in `metrics.yaml` to `SUM(price)` for `order_status = 'delivered'`, because freight fees are shipping pass-through charges rather than merchandise value.
  2. *Delivered Status Filtering:* In GrowthLens, all dashboards filter by `order_status = 'delivered'`. For `delivered_order_rate`, the denominator MUST include all orders; filtering by delivered in WHERE would produce a trivial 100%. `metrics.yaml` documents this pitfall with `COUNT(*) FILTER (WHERE order_status = 'delivered')::DOUBLE / COUNT(*)`.
  3. *Repeat Customer Rate Identification:* In Olist, `customer_id` is a transient 1:1 transaction ID; `customer_unique_id` is the real buyer identifier. GrowthLens cohort and RFM code used `user_id` mapped from `customer_unique_id`. We explicitly documented and implemented grouping on `customer_unique_id`.
  4. *DAU/MAU Metric Nature:* In GrowthLens `data/loader.py`, DAU and MAU are synthetic approximations (`orders * 8` and `dau * 7.2`). Olist has no clickstream session tracking. Out-of-scope questions regarding DAU/MAU will be refused by the text-to-SQL layer as web analytics data is not present.
- **Hand-Checked Verification (2017-10):**
  - GMV: $648,247.65
  - Order Count: 4,478
  - AOV: $144.76
  - Delivered Order Rate: 96.70% (0.9670)
  - Avg Review Score: 4.2052
  - On-Time Delivery Rate: 94.71% (0.9471)
  - Repeat Customer Rate (in-month): 1.36% (0.0136)
- **Tests Passed:** All 6 unit tests in `tests/` passed cleanly.
