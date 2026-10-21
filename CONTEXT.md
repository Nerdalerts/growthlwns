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
