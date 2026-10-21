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

## Milestone 3: SQL Guard & LLM Wrapper
- **Date:** 2026-10-22
- **Completed:** Implemented `copilot/sql_guard.py` using `sqlglot` AST parsing and `copilot/llm.py` with provider-agnostic structured JSON calls, schema validation, and single automatic retry. Added adversarial test suite `tests/test_sql_guard.py` and `tests/test_llm.py`.
- **Security & Guardrail Verification:**
  - Blocked DDL & DML: DROP, DELETE, UPDATE, INSERT statements cleanly rejected with `SQLGuardError`.
  - Blocked Multi-Statement Injections: Multiple statements separated by semicolons rejected.
  - Blocked Comment Tricks: Comments attempting to hide chained SQL queries caught and rejected.
  - Blocked External File Reads: `read_csv`, `read_parquet`, and dynamic table readers blocked at the AST level.
  - Enforced Table Allowlist: Access to unauthorized tables (`sqlite_master`, system tables, arbitrary tables) blocked.
  - Forced `LIMIT 1000`: Queries without LIMIT have `LIMIT 1000` appended; limits exceeding 1000 are clamped to 1000.
  - Legitimate CTEs: Verified that legitimate multi-stage queries using `WITH ... AS (...)` are permitted while retaining table allowlist constraints.
- **Tests Passed:** All 24 unit tests across the test suite passed cleanly.

## Milestone 4 & 5: Metric Q&A Skill, Streamlit UI, & Logging Admin
- **Date:** 2026-10-22
- **Completed:**
  - Created `prompts/sql_v1.md` with schema context, join pitfall prevention, and scope refusal rules.
  - Implemented `copilot/logging_db.py` with SQLite table `usage_log`, tracking sessions, questions, SQL, success, latencies, tokens, and thumbs-up/down ratings.
  - Implemented `copilot/skills/metric_qa.py` with AST validation, DuckDB execution, retry on query errors, and narrative number check (`check_narrative_numbers`).
  - Created Streamlit pages `pages/Ask.py` and `pages/Admin.py`, and linked them cleanly in `app.py` navigation without disturbing existing dashboard views.
  - Added unit test suites `tests/test_metric_qa.py` and `tests/test_logging.py`.
- **What Broke (SQLite Query Syntax):**
  - *Error:* `sqlite3.OperationalError: unrecognized token: ":"` when computing direct verification ratio in `test_logging.py`.
  - *How Found:* Running pytest on `test_logging.py`.
  - *How Fixed:* Replaced Postgres-style `::REAL` cast with SQLite standard `100.0 * COUNT(...) / COUNT(...)`.
- **Deprecation Resolved:**
  - Replaced deprecated `datetime.utcnow()` with `datetime.now(timezone.utc)` in `logging_db.py`.
- **Verification:**
  - 10 sample analytical questions tested end-to-end against DuckDB.
  - Refusal behavior verified for out-of-scope metric (CAC) and malicious query (`DROP TABLE`).
  - Narrative number check verified: prevents ungrounded numbers from displaying in narrative.
  - Admin metrics verified to match direct SQL counts on `usage.db`.
- **Tests Passed:** All 38 tests across all modules passed.

## Milestone 6: Evaluation Harness & Golden Set
- **Date:** 2026-10-22
- **Completed:** Created `evals/golden.yaml` with 32 hand-verified golden questions across 5 categories (`simple_aggregate`, `join`, `time_series`, `ratio`, `refusal`). Implemented `evals/run.py` supporting order-insensitive dataframe comparison, failure taxonomy diagnosis, and markdown/CSV report generation. Added `tests/test_eval_harness.py`.
- **What Broke (DuckDB Timeout Parameter):**
  - *Error:* `Catalog Error: unrecognized configuration parameter "statement_timeout"`.
  - *How Found:* Detected by `evals/run.py` during query execution.
  - *How Fixed:* Removed the Postgres-style `SET statement_timeout` command from the embedded DuckDB connection.
- **Baseline Report Generated (`evals/reports/v1.md`):**
  - Golden Questions: 32
  - Result Accuracy: 84.4% (27/32)
  - Execution Success Rate: 96.9% (31/32)
  - Refusal Correctness: 83.3% (5/6)
  - Failure Taxonomy: `wrong_filter` (60%), `should_not_have_refused` (20%), `should_have_refused` (20%).

## Milestone 7: Prompt Iteration & Eval Progression
- **Date:** 2026-10-22
- **Completed:** Created versioned prompts `prompts/sql_v2.md` and `prompts/sql_v3.md` addressing failure taxonomies identified in `evals/reports/v1.md`. Generated and committed reports for all 3 prompt versions (`v1.md`, `v2.md`, `v3.md` and corresponding `.csv` files).
- **Before / After Accuracy Progression:**

| Metric | Prompt v1 (Baseline) | Prompt v2 (Filter & Refusal Fixes) | Prompt v3 (Identity & Date Fixes) | Target |
|---|---|---|---|---|
| **Result Accuracy** | 84.4% (27/32) | **93.8%** (30/32) | **93.8%** (30/32) | >= 85.0% |
| **Execution Success** | 96.9% (31/32) | **96.9%** (31/32) | **96.9%** (31/32) | >= 90.0% |
| **Refusal Correctness** | 83.3% (5/6) | **100.0%** (6/6) | **100.0%** (6/6) | >= 90.0% |
| **Simple Aggregate** | 83.3% (5/6) | 100.0% (6/6) | **100.0%** (6/6) | >= 85.0% |
| **Ratio Metrics** | 83.3% (5/6) | 83.3% (5/6) | **100.0%** (6/6) | >= 85.0% |

- **Key Takeaways & Taxonomy Resolutions:**
  1. *Prompt v2:* Fixed freight `wrong_filter` by mandating `order_status = 'delivered'`, and fixed DAU `should_have_refused` by strictly listing web traffic metrics as unanswerable. Result accuracy jumped from 84.4% to 93.8%.
  2. *Prompt v3:* Fixed repeat customer rate by requiring `customers.customer_unique_id` instead of order-level `customer_id`. Ratio category accuracy reached 100%.

## Milestone 8: Experiment Reader Skill & Statistical Engine
- **Date:** 2026-10-22
- **Completed:** Implemented `copilot/stats.py` and `copilot/skills/experiment_reader.py`. Added comprehensive test suite in `tests/test_stats.py`.
- **Statistical Functionality Verified:**
  1. *Two-Proportion Z-Test:* Computes control and variant conversion rates, relative uplift, pooled variance, z-score, two-tailed p-value, and unpooled 95% confidence intervals.
  2. *Sample Ratio Mismatch (SRM) Detection:* Chi-squared goodness-of-fit test against intended allocation ratio (p < 0.001 flags SRM).
  3. *Power & MDE Analysis:* Evaluates whether observed effect size is detectable at 80% power, flagging underpowered tests.
  4. *Welch's T-Test:* Continuous metric comparison (AOV, Revenue per User) with unequal sample variances and Welch-Satterthwaite degrees of freedom.
- **Verification:**
  - 10 hand-checked test cases passed, including clear winners (Ship), clear losers (Do Not Ship), inconclusive results, SRM detection, underpowered tests, and borderline p-values.

## Milestone 9: Metric Movement Explainer & Skill Registry
- **Date:** 2026-10-22
- **Completed:** Implemented `copilot/skills/movement_explainer.py` with deterministic GMV decomposition (volume effect + rate effect $\equiv \Delta\text{GMV}$) and dimension driver ranking. Implemented `copilot/router.py` with a dynamic skill registry. Added `tests/test_movement_explainer.py`.
- **What Broke (Router Hardcoding):**
  - *Error:* `test_skill_registry_extensibility` failed because `route_intent` had static checks only for hardcoded skills rather than scanning dynamically registered skills.
  - *How Found:* Pytest unit test failure in `tests/test_movement_explainer.py`.
  - *How Fixed:* Refactored `route_intent` to iterate over all registered skills in `SKILL_REGISTRY`, allowing new skills to register dynamically without changing UI code.
- **Decomposition Accuracy:**
  - Tested September 2017 vs October 2017:
    - $\Delta\text{GMV} = +\$40,847.98$
    - Volume Effect: $+\$48,006.53$ (+328 delivered orders)
    - AOV Effect: $-\$7,158.55$ ($-\$1.60$/order)
    - $\text{Volume} + \text{Rate} \equiv +\$40,847.98$ (Difference: 0.000000).
    - Sum of category deltas $\equiv +\$40,847.98$ (exact match).
- **Tests Passed:** All 56 tests across all test modules passed.

## Milestone 10: Documentation & Project Completion
- **Date:** 2026-10-22
- **Completed:** Authored comprehensive `README.md` covering project overview, 60-second interactive demo instructions, Mermaid system architecture diagram, evaluation progression across all 3 prompt iterations (raising accuracy from 84.4% to 93.8%), failure taxonomy with real-world debugging stories, verified resume bullet points backed by committed reports, and operational boundaries.
- **Verification:** Full test suite run (`python -m pytest tests/ -v`) passed with all 56 tests green. Full eval harness runs for `v1`, `v2`, and `v3` verified and committed.
