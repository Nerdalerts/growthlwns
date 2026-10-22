# GrowthLens Prompts

- **`sql_system.md`**: The primary, active text-to-SQL system prompt used across the GrowthLens Copilot application and test suite. Contains all schema rules, DuckDB dialect constraints, repeat buyer disambiguation (`customer_unique_id`), delivered order filtering, and refusal policies.
- **`history/`**: Contains versioned evaluation snapshots (`sql_v1.md`, `sql_v2.md`, `sql_v3.md`) benchmarked by the LLM evaluation harness (`evals/run.py`).
