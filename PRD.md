# PRD: GrowthLens Copilot (AI analytics skills on top of GrowthLens)

**Owner:** Adarsh · **Status:** v1 draft · **Build window:** ~2-3 weeks (P0 shippable in ~1 week)
**One-line pitch:** Turn the repeated analytics questions a PM asks every week into AI "skills" anyone can invoke in plain English, with every number traceable, every answer evaluated, and every use logged.

---

## 0. How to use this document with an AI IDE

1. Put this file in the repo root as `PRD.md`. Also create a `CONTEXT.md` containing only **Section 12 (Context block)**.
2. Work one milestone at a time using the **Prompt Pack (Section 13)**. Paste the Context block, then the milestone prompt. Do not ask the IDE to "build everything".
3. After each milestone: run the tests, commit, and only then move on.
4. Keep a `BUILD_LOG.md`. Every time something breaks, log: what broke, how it was found, how it was fixed. This is interview material.

---

## 1. Problem statement

Product managers and analysts repeatedly ask the same kinds of questions: "What was GMV last month?", "Which category drove the AOV drop?", "Is this A/B test result real?". Today each one needs a person to write a query, check it, and explain it. The work is repetitive, slow, and answers vary by who wrote the query because metric definitions live in people's heads.

GrowthLens already provides the dashboards (North Star, funnel, cohorts, A/B testing, RFM, revenue and product analytics) on the Olist e-commerce dataset (~99K orders). It is view-only: a user can only see what was pre-built.

**Goal of this project:** add a layer that turns repeated analytical work into invokable skills, and prove the skills are correct and used. Work is judged on **adoption and correctness**, not effort.

## 2. Target users

| Persona | Need |
|---|---|
| PM (primary) | Quick, trustworthy answers to metric questions without waiting on an analyst |
| Analyst (secondary) | Offload repetitive lookups; inspect the SQL to verify |
| Reviewer (the author, in demos) | See accuracy, failure modes and usage data in one place |

Pilot users: 5-10 real people (classmates, society members, friends in product/data roles). Metrics in this PRD are only claimed after a real pilot.

## 3. Goals

1. **Correct answers:** at least 85% result-accuracy on a hand-built golden set of 30+ questions by the end of P0 (stretch: 90%).
2. **Trustworthy:** 100% of numeric answers show the SQL and the raw result table; the LLM never computes or invents numbers itself.
3. **Safe:** 0 write/DDL statements ever executed; 100% of out-of-scope or unanswerable questions are refused with a reason, not guessed.
4. **Used:** at least 5 distinct pilot users and 50+ logged questions within 2 weeks of P0 launch.
5. **Measurable and improvable:** a repeatable eval run that shows accuracy changing across prompt versions, with a failure taxonomy.

## 4. Non-goals

- No dashboard rebuild or redesign of existing GrowthLens pages (out of scope: the value is the skills layer).
- No fine-tuning or training models (premature; prompting plus evals is enough).
- No auth, multi-tenant users or cloud deployment in v1 (adds work, no learning on the core problem).
- No connection to any real company data warehouse. Olist CSVs only (privacy and reproducibility).
- No autonomous actions (no emailing, no writing back to data). Read-only analysis only.

## 5. User stories

**PM**
- As a PM, I want to ask "What was monthly GMV and AOV in 2017?" in plain English so that I get a number and chart without writing SQL.
- As a PM, I want to see the SQL and the metric definition used so that I can trust or challenge the answer.
- As a PM, I want to paste an A/B test's counts and get a plain-English verdict with the real statistics so that I know whether to ship.
- As a PM, I want to ask "why did GMV change between month X and Y?" and see a ranked breakdown so that I know where to dig.
- As a PM, I want a clear refusal when a question can't be answered from the data so that I'm never given a made-up number.

**Analyst**
- As an analyst, I want to flag an answer as wrong with a reason so that it enters the failure log and improves the system.

**Author**
- As the author, I want an admin page with accuracy, usage and failure types so that I can show adoption and correctness in a review.

## 6. Requirements

### P0 (must ship)

**P0-1. Data layer.**
- Load Olist CSVs into DuckDB (file `data/olist.duckdb`), tables named as in the CSVs (orders, order_items, order_payments, customers, products, sellers, order_reviews, product_category_name_translation).
- Acceptance: `python -m copilot.data.build` is idempotent; row counts are printed and match the CSVs.

**P0-2. Metrics semantic layer (single source of truth).**
- `metrics.yaml` defines each metric once: name, description, SQL expression, grain, filters, known pitfalls. Minimum: GMV, order_count, AOV, delivered_order_rate, avg_review_score, repeat_customer_rate, on_time_delivery_rate.
- Reuse the definitions already used by the existing GrowthLens pages. Where GrowthLens and `metrics.yaml` disagree, GrowthLens is audited and the discrepancy is logged in `BUILD_LOG.md`.
- Acceptance: unit tests compute every metric and compare to a hand-checked value for at least one month.

**P0-3. Skill 1: Metric Q&A (text-to-SQL).**
- Flow: question -> scope check -> prompt with schema + metrics.yaml -> LLM returns structured JSON (`sql`, `metric_used`, `assumptions`, `refusal_reason`) -> SQL validation -> execute -> result table + auto chart + short narrative.
- Guardrails: SELECT-only (parse with `sqlglot`), table allowlist, forced `LIMIT 1000`, 10s timeout, read-only DuckDB connection, one automatic retry that feeds the error message back.
- The narrative is generated from the result table only. Numbers in the narrative must appear in the result (validated by a simple regex check; mismatch -> show table only and log `narrative_mismatch`).
- Refusals: questions needing data not in the dataset (e.g. "what is our CAC?") return a refusal with the reason.
- Acceptance (Given/When/Then):
  - Given a valid question, when asked, then the UI shows answer, SQL, result table and metric definition.
  - Given a prompt-injection or "drop table" request, when asked, then nothing is executed and the refusal is logged.
  - Given an unanswerable question, when asked, then a refusal with a reason is shown, never a guessed number.

**P0-4. Eval harness.**
- `evals/golden.yaml`: 30+ questions, each with hand-written ground-truth SQL, category tag (simple aggregate, join, time series, ratio, refusal) and difficulty.
- `python -m evals.run --prompt-version vN` executes all, compares result sets (order-insensitive, numeric tolerance 1e-6 relative), and writes `evals/reports/vN.md` + `.csv` with: execution success rate, result accuracy, refusal correctness, accuracy by category, and each failure tagged with a taxonomy label.
- Failure taxonomy (minimum): `wrong_join`, `fan_out_double_count`, `wrong_metric_definition`, `date_handling`, `hallucinated_column`, `wrong_filter`, `should_have_refused`, `should_not_have_refused`.
- Acceptance: running twice on the same prompt version gives results within noise; reports for at least 3 prompt versions are committed.

**P0-5. Usage logging and admin page.**
- SQLite `logs/usage.db`, table `usage_log`: `ts, session_id, skill, question, generated_sql, success, error_type, latency_ms, input_tokens, output_tokens, thumbs, user_comment`.
- Streamlit admin page: questions per day, distinct sessions, success rate, thumbs-up rate, p50/p95 latency, top failure types, a table of thumbs-down questions.
- Thumbs up/down with an optional comment on every answer.
- Acceptance: killing and restarting the app keeps history; admin page numbers match a direct SQL count on the log DB.

### P1 (fast follows)

**P1-1. Skill 2: Experiment Reader.** User enters (or selects from the existing A/B module) control/treatment sample sizes and conversions or means. Statistics are computed in code (two-proportion z-test or Welch t-test, effect size, confidence interval, minimum detectable effect at given power, sample ratio mismatch check). The LLM only writes the verdict from those computed values and must state when the result is inconclusive or underpowered. Acceptance: 10 hand-checked cases (including one with SRM and one underpowered) produce correct verdicts.

**P1-2. Skill 3: Metric Movement Explainer.** Given a metric and two periods, decompose the change deterministically (e.g. GMV = orders x AOV; then by category, state, payment type), rank contributors, and let the LLM narrate the top 3. Acceptance: contributions sum to the total change within rounding.

**P1-3. Skill registry.** `skills/` folder where each skill is one file declaring `name`, `description`, `input_schema`, `run()`. The router picks a skill from the user's text, or asks one clarifying question if ambiguous. Adding a skill requires no changes to the UI code.

### P2 (design for, don't build)

- Saved/shared questions, scheduled weekly digest, a second dataset (used-car listings), cost dashboard per skill, multi-turn follow-up questions ("now split that by state").

## 7. Success metrics

| Type | Metric | Target (hypothesis) | How measured |
|---|---|---|---|
| Leading | Golden-set result accuracy | >= 85% (stretch 90%) | `evals/reports` |
| Leading | Refusal correctness | >= 90% | eval report |
| Leading | Execution success rate (live) | >= 90% | `usage_log.success` |
| Leading | Pilot adoption | >= 5 users, 50+ questions in 2 weeks | `usage_log` |
| Leading | Thumbs-up rate | >= 70% of rated answers | `usage_log.thumbs` |
| Lagging | Repeat usage | >= 2 of pilot users return on a second day | sessions by day |
| Lagging | Accuracy trend | each prompt version >= previous, regressions explained | reports |

Targets are starting hypotheses. Whatever the real numbers turn out to be is what goes on the resume.

## 8. Technical approach

- **Language/stack:** Python 3.11+, Streamlit, DuckDB, pandas, sqlglot, pydantic, pyyaml, scipy (stats), pytest, plotly or altair (charts), anthropic SDK.
- **LLM access:** thin wrapper `copilot/llm.py` reading `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` from environment (check Anthropic's docs for the current model string; do not hardcode). Keep the wrapper provider-agnostic so a model can be swapped in one place.
- **Structured output:** ask for JSON, validate with pydantic, retry once on schema failure.
- **Determinism:** temperature 0 for SQL generation. All numbers come from DuckDB or scipy, never from the LLM.
- **Prompt assets:** prompts live in `prompts/` as versioned files (`sql_v1.md`, `sql_v2.md`) with a changelog; the eval harness takes the prompt version as a parameter.
- **Known Olist pitfalls to encode in `metrics.yaml` and prompts:** joining `order_items` to `order_payments` multiplies rows (fan-out) and inflates revenue; only some orders are `delivered`; delivery and review dates can be null; timestamps are stored as strings in the CSVs and need casting; product category names need the translation table. Verify each against the actual data before relying on it.
- **Security:** `.env` is git-ignored, `.env.example` committed; never log API keys; log questions locally only.

Suggested structure:

```
growthlens/                 # existing repo, keep working
copilot/
  data/build.py
  llm.py
  router.py
  sql_guard.py
  logging_db.py
  skills/{metric_qa.py, experiment_reader.py, movement_explainer.py}
metrics.yaml
prompts/
evals/{golden.yaml, run.py, reports/}
pages/{Ask.py, Admin.py}    # Streamlit pages
tests/
PRD.md  CONTEXT.md  BUILD_LOG.md  README.md
```

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| LLM writes plausible but wrong SQL | Golden-set evals, SQL always shown, metric definitions injected, failure taxonomy |
| Revenue double-counting from joins | Pitfall documented in `metrics.yaml`; dedicated golden questions |
| Prompt injection / destructive SQL | SELECT-only AST check, read-only connection, allowlist |
| API cost and rate limits | Cache identical questions, cap tokens, log tokens per call |
| No real users | Pilot plan in Section 11; claim only measured numbers |
| Scope creep | P1/P2 are fenced; each milestone has a definition of done |

## 10. Open questions

- **Blocking (author):** which GrowthLens metric definitions are canonical when they differ from a naive SQL reading? Resolve in Milestone 2.
- **Non-blocking (author):** does a second, used-car dataset make the demo more relevant, or is Olist enough? Decide after P0.
- **Non-blocking (data):** should delivery performance questions be in scope for P0 or deferred to P1? Default: in scope for golden set only.

## 11. Timeline and pilot plan

- **Week 1 (P0):** Milestones 1-5 (data, metrics, Metric Q&A, evals, logging/admin). Ship, record a 60-90 second demo.
- **Week 2:** Pilot with 5-10 users; read the thumbs-down log; do at least two prompt iterations driven by the failure taxonomy.
- **Week 3 (P1):** Experiment Reader, then Movement Explainer, skill registry. Write the README with the eval table and a "what broke" section.

## 12. Context block (paste at the start of every IDE session)

```
PROJECT: GrowthLens Copilot, an AI skills layer on the existing GrowthLens Streamlit app (Olist e-commerce dataset, ~99K orders).
READ FIRST: PRD.md, metrics.yaml, BUILD_LOG.md. Inspect the existing repo before creating files; reuse existing metric logic and do not break existing GrowthLens pages.
STACK: Python 3.11+, Streamlit, DuckDB, pandas, sqlglot, pydantic, pyyaml, scipy, pytest, anthropic SDK.
RULES:
- The LLM never computes numbers. All numbers come from DuckDB/scipy and are shown with SQL and a result table.
- SQL must be SELECT-only, allowlisted tables, LIMIT enforced, read-only connection, timeout.
- Model name and API key come from environment variables. Never hardcode secrets.
- Small, readable functions. Add pytest tests for every module. No new dependencies without saying why.
- Before writing code for a milestone: list the files you will create/change and wait for my OK.
- After finishing: run tests, summarize what changed, and append anything that broke to BUILD_LOG.md.
- If a requirement is ambiguous or data contradicts the PRD, stop and ask. Do not guess.
```

## 13. Prompt pack (one prompt per milestone)

**M0. Repo audit.**
"Read the repo and PRD.md. Produce: (1) a map of existing modules and how metrics like GMV, AOV, DAU/MAU are currently computed, (2) where the data files live, (3) a proposed folder layout for `copilot/` that does not disturb existing pages, (4) risks. Do not write code yet."

**M1. Data layer.**
"Implement `copilot/data/build.py` to load the Olist CSVs into DuckDB at `data/olist.duckdb`, casting timestamps correctly, idempotent, printing row counts. Add tests comparing row counts to CSVs. Definition of done: tests pass and the script runs twice cleanly."

**M2. Metrics semantic layer.**
"Create `metrics.yaml` with GMV, order_count, AOV, delivered_order_rate, avg_review_score, repeat_customer_rate, on_time_delivery_rate, each with description, SQL, grain, filters and pitfalls. Add `copilot/metrics.py` to load and compute them. Compare against the existing GrowthLens computations and list any discrepancies in BUILD_LOG.md. Add tests with hand-checked values for one month."

**M3. SQL guard and LLM wrapper.**
"Implement `copilot/sql_guard.py` (sqlglot AST: SELECT only, table allowlist, forced LIMIT, no multiple statements, no functions that read files) and `copilot/llm.py` (env-based config, pydantic-validated JSON output, one retry, token counting). Write adversarial tests: DROP, DELETE, multi-statement, comment tricks, reading external files. Definition of done: all adversarial tests are blocked."

**M4. Metric Q&A skill + UI.**
"Implement `copilot/skills/metric_qa.py` per PRD P0-3 and a Streamlit page `pages/Ask.py` showing answer, SQL (collapsible), result table, auto chart, the metric definition used, and thumbs up/down. Include the narrative number-check. Use prompt file `prompts/sql_v1.md`. Definition of done: 10 sample questions work end-to-end and the refusal cases behave."

**M5. Logging and admin.**
"Implement `copilot/logging_db.py` (SQLite, schema from PRD P0-5) and `pages/Admin.py` with the listed charts and a thumbs-down table. Log every call including failures and refusals. Definition of done: admin numbers match direct SQL counts on the log DB."

**M6. Eval harness.**
"Create `evals/golden.yaml` skeleton with 30+ questions across simple aggregate, join, time series, ratio and refusal categories (I will write and verify the ground-truth SQL myself; leave `ground_truth_sql` blank where unsure). Implement `evals/run.py` as specified in P0-4, including the failure taxonomy and markdown/CSV reports. Definition of done: a report for `v1` is generated."

**M7. Iterate (repeat).**
"Read `evals/reports/vN.md`. Group failures by taxonomy. Propose at most 3 prompt or metrics.yaml changes that address the largest groups, create `prompts/sql_v(N+1).md` with a changelog entry, re-run evals, and show a before/after table. Do not change the golden set to make scores rise."

**M8. Experiment Reader (P1).**
"Implement skill per P1-1. Stats in `copilot/stats.py` with tests against hand-computed cases, including SRM and underpowered. The LLM receives only the computed values and writes the verdict; it must flag inconclusive results."

**M9. Movement Explainer (P1).**
"Implement skill per P1-2 with deterministic decomposition and a test that contributions sum to the total change."

**M10. Docs.**
"Write README.md: what it is, a 60-second demo section, architecture diagram (mermaid), the eval results table across prompt versions, the failure taxonomy with real examples from BUILD_LOG.md, how to run, limitations. No claims that are not backed by a committed report or log."

## 14. Resume and interview claims policy

- Write bullets only after you have real numbers from `evals/reports` and `usage.db`.
- Template (fill only with measured values):
  - "Built an AI analytics layer on GrowthLens: natural-language questions to validated, read-only SQL over [N] Olist orders, with SQL and definitions shown for every answer."
  - "Wrote a [N]-question golden eval set and raised result accuracy from [X]% to [Y]% across [K] prompt versions, tagging failures (e.g. join fan-out) to drive fixes."
  - "Piloted with [N] users ([M] questions logged); [Z]% thumbs-up; used failure logs to fix [specific issue]."
- Interview story to prepare: the single most instructive thing that broke (from `BUILD_LOG.md`), how you detected it, and what you changed.
