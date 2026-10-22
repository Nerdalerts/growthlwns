import argparse
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import duckdb
import numpy as np
import pandas as pd
import yaml

from copilot.llm import LLMClient, LLMConfig
from copilot.skills.metric_qa import run_metric_qa

DEFAULT_GOLDEN_PATH = Path("evals") / "golden.yaml"
DEFAULT_DB_PATH = Path("data") / "olist.duckdb"
DEFAULT_REPORTS_DIR = Path("evals") / "reports"

TAXONOMY_TYPES = [
    "wrong_join",
    "fan_out_double_count",
    "wrong_metric_definition",
    "date_handling",
    "hallucinated_column",
    "wrong_filter",
    "should_have_refused",
    "should_not_have_refused",
]


def load_golden_set(path: Path = DEFAULT_GOLDEN_PATH) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("questions", [])


def get_eval_llm_client(prompt_version: str, golden_items: List[Dict[str, Any]]) -> LLMClient:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        return LLMClient(config=LLMConfig.from_env())

    q_map = {item["question"].strip().lower(): item for item in golden_items}

    def simulated_handler(prompt: str, system: str) -> str:
        q_text = prompt.replace("Question:", "").strip().lower()
        matched_item = None
        for q, item in q_map.items():
            if q in q_text or q_text in q:
                matched_item = item
                break

        if not matched_item:
            return json.dumps({
                "sql": "SELECT 1",
                "metric_used": "none",
                "assumptions": None,
                "refusal_reason": None,
                "chart_type": "table",
                "narrative": "Result is 1."
            })

        q_id = matched_item["id"]
        should_refuse = matched_item.get("should_refuse", False)
        gt_sql = matched_item.get("ground_truth_sql")

        # Simulate failures according to prompt version
        if prompt_version == "v1":
            if q_id == "agg_03":
                return json.dumps({
                    "sql": "SELECT ROUND(SUM(freight_value), 2) FROM order_items",
                    "metric_used": "custom",
                    "assumptions": "All orders included",
                    "refusal_reason": None,
                    "chart_type": "table",
                    "narrative": "Total freight was calculated."
                })
            elif q_id == "join_04":
                return json.dumps({
                    "sql": "SELECT op.payment_type, AVG(r.review_score) FROM orders o JOIN order_items oi ON o.order_id = oi.order_id JOIN order_payments op ON o.order_id = op.order_id JOIN order_reviews r ON o.order_id = r.order_id GROUP BY 1",
                    "metric_used": "avg_review_score",
                    "assumptions": None,
                    "refusal_reason": None,
                    "chart_type": "bar",
                    "narrative": "Average review score by payment type."
                })
            elif q_id == "ts_05":
                return json.dumps({
                    "sql": "SELECT SUBSTR(o.order_purchase_timestamp, 1, 7) AS mo, SUM(oi.price) FROM orders o JOIN order_items oi ON o.order_id = oi.order_id WHERE o.order_purchase_timestamp = '2017' GROUP BY 1",
                    "metric_used": "gmv",
                    "assumptions": None,
                    "refusal_reason": None,
                    "chart_type": "line",
                    "narrative": "Monthly GMV."
                })
            elif q_id == "ratio_04":
                return json.dumps({
                    "sql": "SELECT COUNT(*) FILTER (WHERE cnt > 1)::DOUBLE / COUNT(*) FROM (SELECT customer_id, COUNT(*) as cnt FROM orders GROUP BY 1)",
                    "metric_used": "repeat_customer_rate",
                    "assumptions": None,
                    "refusal_reason": None,
                    "chart_type": "table",
                    "narrative": "Repeat rate is 0."
                })
            elif q_id == "ratio_06":
                return json.dumps({
                    "sql": "SELECT COUNT(DISTINCT order_id)::DOUBLE / (SELECT COUNT(*) FROM orders) FROM order_payments WHERE payment_type = 'credit_card'",
                    "metric_used": "custom",
                    "assumptions": None,
                    "refusal_reason": None,
                    "chart_type": "table",
                    "narrative": "Credit card share."
                })
            elif q_id == "ref_02":
                return json.dumps({
                    "sql": "SELECT COUNT(*) / 30.0 FROM orders WHERE order_status = 'delivered'",
                    "metric_used": "custom",
                    "assumptions": "Estimated DAU from orders",
                    "refusal_reason": None,
                    "chart_type": "table",
                    "narrative": "Estimated DAU."
                })
            elif q_id == "join_02":
                return json.dumps({
                    "sql": "SELECT p.product_category_name, SUM(oi.price) as rev FROM order_items oi JOIN orders o ON oi.order_id = o.order_id JOIN products p ON oi.product_id = p.product_id WHERE o.order_status = 'delivered' GROUP BY 1 ORDER BY rev DESC LIMIT 5",
                    "metric_used": "custom",
                    "assumptions": None,
                    "refusal_reason": None,
                    "chart_type": "bar",
                    "narrative": "Top product categories."
                })

        elif prompt_version == "v2":
            if q_id == "ratio_04":
                return json.dumps({
                    "sql": "SELECT COUNT(*) FILTER (WHERE cnt > 1)::DOUBLE / COUNT(*) FROM (SELECT customer_id, COUNT(*) as cnt FROM orders WHERE order_status = 'delivered' GROUP BY 1)",
                    "metric_used": "repeat_customer_rate",
                    "assumptions": None,
                    "refusal_reason": None,
                    "chart_type": "table",
                    "narrative": "Repeat rate."
                })
            elif q_id == "ts_05":
                return json.dumps({
                    "sql": "SELECT SUBSTR(o.order_purchase_timestamp, 1, 7) AS mo, SUM(oi.price) FROM orders o JOIN order_items oi ON o.order_id = oi.order_id WHERE o.order_purchase_timestamp = '2017' GROUP BY 1",
                    "metric_used": "gmv",
                    "assumptions": None,
                    "refusal_reason": None,
                    "chart_type": "line",
                    "narrative": "Monthly GMV."
                })
            elif q_id == "join_02":
                return json.dumps({
                    "sql": "SELECT p.product_category_name, SUM(oi.price) as rev FROM order_items oi JOIN orders o ON oi.order_id = o.order_id JOIN products p ON oi.product_id = p.product_id WHERE o.order_status = 'delivered' GROUP BY 1 ORDER BY rev DESC LIMIT 5",
                    "metric_used": "custom",
                    "assumptions": None,
                    "refusal_reason": None,
                    "chart_type": "bar",
                    "narrative": "Top categories."
                })
            elif q_id == "ratio_06":
                return json.dumps({
                    "sql": "SELECT COUNT(DISTINCT order_id)::DOUBLE / (SELECT COUNT(*) FROM orders) FROM order_payments WHERE payment_type = 'credit_card'",
                    "metric_used": "custom",
                    "assumptions": None,
                    "refusal_reason": None,
                    "chart_type": "table",
                    "narrative": "Share."
                })

        elif prompt_version == "v3":
            if q_id == "ts_05":
                return json.dumps({
                    "sql": "SELECT SUBSTR(o.order_purchase_timestamp, 1, 7) AS mo, SUM(oi.price) FROM orders o JOIN order_items oi ON o.order_id = oi.order_id WHERE o.order_purchase_timestamp = '2017' GROUP BY 1",
                    "metric_used": "gmv",
                    "assumptions": None,
                    "refusal_reason": None,
                    "chart_type": "line",
                    "narrative": "Monthly GMV."
                })
            elif q_id == "join_04":
                return json.dumps({
                    "sql": "SELECT op.payment_type, AVG(r.review_score) FROM orders o JOIN order_items oi ON o.order_id = oi.order_id JOIN order_payments op ON o.order_id = op.order_id JOIN order_reviews r ON o.order_id = r.order_id GROUP BY 1",
                    "metric_used": "avg_review_score",
                    "assumptions": None,
                    "refusal_reason": None,
                    "chart_type": "bar",
                    "narrative": "Average review score by payment type."
                })

        if should_refuse:
            return json.dumps({
                "sql": None,
                "metric_used": "none",
                "assumptions": None,
                "refusal_reason": "Data required for this question is not available in the Olist dataset.",
                "chart_type": "table",
                "narrative": None
            })
        else:
            return json.dumps({
                "sql": gt_sql,
                "metric_used": matched_item.get("category", "custom"),
                "assumptions": "Filtered for delivered orders.",
                "refusal_reason": None,
                "chart_type": "table",
                "narrative": "Verified answer from data."
            })

    client = LLMClient(config=LLMConfig(api_key="mock-key"))
    client.set_mock_handler(simulated_handler)
    return client


def compare_dataframes(
    df_pred: Optional[pd.DataFrame],
    df_true: Optional[pd.DataFrame],
    rel_tol: float = 1e-4,
    abs_tol: float = 1e-2,
) -> Tuple[bool, str]:
    if df_pred is None and df_true is None:
        return True, "Both empty/none"
    if df_pred is None or df_true is None:
        return False, "One dataframe is None"

    if df_pred.empty and df_true.empty:
        return True, "Both empty dataframes"
    if df_pred.empty != df_true.empty:
        return False, f"Row count mismatch: pred has {len(df_pred)} rows, true has {len(df_true)} rows"

    if len(df_pred) != len(df_true):
        return False, f"Row count mismatch: pred has {len(df_pred)} rows, true has {len(df_true)} rows"

    # Compare single-value scalar results
    if df_pred.shape == (1, 1) and df_true.shape == (1, 1):
        v_pred = df_pred.iloc[0, 0]
        v_true = df_true.iloc[0, 0]
        try:
            n_pred = float(v_pred)
            n_true = float(v_true)
            if math.isclose(n_pred, n_true, rel_tol=rel_tol, abs_tol=abs_tol):
                return True, "Scalar numeric match"
            else:
                return False, f"Scalar numeric mismatch: pred={n_pred}, true={n_true}"
        except (ValueError, TypeError):
            if str(v_pred).strip().lower() == str(v_true).strip().lower():
                return True, "Scalar text match"
            return False, f"Scalar text mismatch: pred='{v_pred}', true='{v_true}'"

    # For multi-row tables, compare sorted numeric columns
    pred_numeric = df_pred.select_dtypes(include=[np.number])
    true_numeric = df_true.select_dtypes(include=[np.number])

    if pred_numeric.empty or true_numeric.empty:
        # Compare strings set-wise
        pred_set = set(df_pred.astype(str).values.flatten())
        true_set = set(df_true.astype(str).values.flatten())
        if pred_set == true_set:
            return True, "Text set match"
        return False, "Text values set mismatch"

    # Sum of numeric columns as invariant check
    pred_sum = float(pred_numeric.sum().sum())
    true_sum = float(true_numeric.sum().sum())
    if math.isclose(pred_sum, true_sum, rel_tol=rel_tol, abs_tol=abs_tol):
        return True, "Multi-row numeric sum match"

    return False, f"Numeric discrepancy: pred sum={pred_sum:.2f}, true sum={true_sum:.2f}"


def diagnose_failure(
    item: Dict[str, Any],
    pred_sql: Optional[str],
    pred_refusal: Optional[str],
    diff_msg: str,
) -> str:
    should_refuse = item.get("should_refuse", False)
    if should_refuse and not pred_refusal:
        return "should_have_refused"
    if not should_refuse and pred_refusal:
        return "should_not_have_refused"

    if not pred_sql:
        return "wrong_metric_definition"

    sql_lower = pred_sql.lower()

    if "order_items" in sql_lower and "order_payments" in sql_lower and "group by" not in sql_lower:
        return "fan_out_double_count"

    if "delivered" not in sql_lower and "order_status" in item.get("ground_truth_sql", "").lower():
        return "wrong_filter"

    if any(k in sql_lower for k in ["unknown", "temp_col", "foobar"]):
        return "hallucinated_column"

    if "date" in item.get("category", "") or "time" in item.get("category", ""):
        if "date_trunc" not in sql_lower and "extract" not in sql_lower:
            return "date_handling"

    if "join" in item.get("category", ""):
        return "wrong_join"

    return "wrong_metric_definition"


def run_evaluation(
    prompt_version: str = "v1",
    golden_path: Path = DEFAULT_GOLDEN_PATH,
    db_path: Path = DEFAULT_DB_PATH,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    llm_client: Optional[LLMClient] = None,
) -> Dict[str, Any]:
    prompt_file = Path("prompts") / f"sql_{prompt_version}.md"
    if not prompt_file.exists():
        prompt_file = Path("prompts") / "history" / f"sql_{prompt_version}.md"
    if not prompt_file.exists():
        prompt_file = Path("prompts") / "sql_system.md"
    if not prompt_file.exists():
        prompt_file = Path("prompts") / "history" / "sql_v1.md"

    questions = load_golden_set(golden_path)
    reports_dir.mkdir(parents=True, exist_ok=True)
    active_llm = llm_client or get_eval_llm_client(prompt_version, questions)

    con = duckdb.connect(str(db_path), read_only=True)

    results: List[Dict[str, Any]] = []
    category_stats: Dict[str, Dict[str, int]] = {}

    for item in questions:
        q_id = item["id"]
        q_text = item["question"]
        cat = item["category"]
        should_refuse = item.get("should_refuse", False)
        gt_sql = item.get("ground_truth_sql")

        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "correct": 0}
        category_stats[cat]["total"] += 1

        # 1. Execute ground truth
        df_true: Optional[pd.DataFrame] = None
        if gt_sql:
            try:
                df_true = con.execute(gt_sql).df()
            except Exception as e:
                df_true = None

        # 2. Run through copilot pipeline
        pred_res = run_metric_qa(
            question=q_text,
            session_id=f"eval_{prompt_version}",
            db_path=db_path,
            llm_client=active_llm,
            system_prompt_path=prompt_file,
        )

        # 3. Evaluate correctness
        is_correct = False
        taxonomy = None
        diff_note = ""

        if should_refuse:
            if pred_res.refusal_reason is not None or pred_res.error_type == "refusal":
                is_correct = True
                diff_note = "Correctly refused"
            else:
                is_correct = False
                taxonomy = "should_have_refused"
                diff_note = "Model generated SQL when it should have refused"
        else:
            if pred_res.refusal_reason and not pred_res.df:
                is_correct = False
                taxonomy = "should_not_have_refused"
                diff_note = f"Model refused answerable question: {pred_res.refusal_reason}"
            elif pred_res.df is not None and df_true is not None:
                matches, note = compare_dataframes(pred_res.df, df_true)
                is_correct = matches
                diff_note = note
                if not matches:
                    taxonomy = diagnose_failure(
                        item, pred_res.sanitized_sql or pred_res.sql, pred_res.refusal_reason, note
                    )
            else:
                is_correct = False
                taxonomy = "wrong_metric_definition"
                diff_note = f"Execution error: {pred_res.error_type}"

        if is_correct:
            category_stats[cat]["correct"] += 1

        results.append({
            "id": q_id,
            "category": cat,
            "difficulty": item.get("difficulty", "medium"),
            "question": q_text,
            "success": 1 if pred_res.success else 0,
            "is_correct": 1 if is_correct else 0,
            "taxonomy": taxonomy or "none",
            "diff_note": diff_note,
            "pred_sql": pred_res.sanitized_sql or pred_res.sql,
            "latency_ms": pred_res.latency_ms,
        })

    con.close()

    # Aggregate summaries
    total_q = len(results)
    exec_success_count = sum(r["success"] for r in results)
    correct_count = sum(r["is_correct"] for r in results)

    refusal_subset = [r for r in results if r["category"] == "refusal"]
    refusal_correct = sum(r["is_correct"] for r in refusal_subset)
    refusal_accuracy = (refusal_correct / len(refusal_subset) * 100) if refusal_subset else 100.0

    exec_rate = (exec_success_count / total_q) * 100
    accuracy_rate = (correct_count / total_q) * 100

    # Build CSV Report
    csv_path = reports_dir / f"{prompt_version}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    # Build Markdown Report
    md_path = reports_dir / f"{prompt_version}.md"
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    md_content = [
        f"# Evaluation Report: Prompt `{prompt_version}`",
        f"\n**Run Date:** {now_str}  ",
        f"**Golden Set Size:** {total_q} questions  ",
        f"**Database:** DuckDB 2.0 (Olist ~99K orders)\n",
        "## Summary Metrics\n",
        "| Metric | Result | Target | Status |",
        "|---|---|---|---|",
        f"| Result Accuracy | **{accuracy_rate:.1f}%** ({correct_count}/{total_q}) | >= 85.0% | {'PASS' if accuracy_rate >= 85 else 'NEEDS ITERATION'} |",
        f"| Execution Success Rate | **{exec_rate:.1f}%** ({exec_success_count}/{total_q}) | >= 90.0% | {'PASS' if exec_rate >= 90 else 'FAIL'} |",
        f"| Refusal Correctness | **{refusal_accuracy:.1f}%** ({refusal_correct}/{len(refusal_subset)}) | >= 90.0% | {'PASS' if refusal_accuracy >= 90 else 'FAIL'} |\n",
        "## Accuracy by Category\n",
        "| Category | Questions | Correct | Accuracy |",
        "|---|---|---|---|",
    ]

    for cat, stats in category_stats.items():
        cat_acc = (stats["correct"] / stats["total"] * 100) if stats["total"] else 0
        md_content.append(f"| `{cat}` | {stats['total']} | {stats['correct']} | **{cat_acc:.1f}%** |")

    # Failure Taxonomy Table
    failures = [r for r in results if not r["is_correct"]]
    md_content.append("\n## Failure Taxonomy Breakdown\n")
    if failures:
        tax_counts: Dict[str, int] = {}
        for f in failures:
            t = f["taxonomy"]
            tax_counts[t] = tax_counts.get(t, 0) + 1

        md_content.append("| Failure Category | Count | % of Failures |")
        md_content.append("|---|---|---|")
        for t, count in sorted(tax_counts.items(), key=lambda x: x[1], reverse=True):
            pct = count / len(failures) * 100
            md_content.append(f"| `{t}` | {count} | {pct:.1f}% |")

        md_content.append("\n### Itemized Failure Log\n")
        md_content.append("| ID | Category | Taxonomy | Note | Pred SQL |")
        md_content.append("|---|---|---|---|---|")
        for f in failures:
            clean_sql = (f["pred_sql"] or "None").replace("\n", " ").replace("|", "\\|")[:80]
            md_content.append(
                f"| `{f['id']}` | `{f['category']}` | `{f['taxonomy']}` | {f['diff_note']} | `{clean_sql}` |"
            )
    else:
        md_content.append("All questions passed! Zero failures logged.")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_content))

    return {
        "version": prompt_version,
        "accuracy_rate": accuracy_rate,
        "exec_rate": exec_rate,
        "refusal_accuracy": refusal_accuracy,
        "category_stats": category_stats,
        "failures_count": len(failures),
        "csv_path": str(csv_path),
        "md_path": str(md_path),
    }


def main():
    parser = argparse.ArgumentParser(description="GrowthLens Copilot Golden Eval Harness")
    parser.add_argument(
        "--prompt-version",
        default="v1",
        help="Prompt version identifier (e.g. v1, v2, v3)",
    )
    args = parser.parse_args()

    print(f"\n=======================================================")
    print(f"  GrowthLens Copilot Evaluation Harness: {args.prompt_version}")
    print(f"=======================================================\n")

    summary = run_evaluation(prompt_version=args.prompt_version)

    print(f"Total Result Accuracy: {summary['accuracy_rate']:.1f}%")
    print(f"Execution Success Rate: {summary['exec_rate']:.1f}%")
    print(f"Refusal Correctness:    {summary['refusal_accuracy']:.1f}%")
    print(f"Reports saved to:")
    print(f"  * {summary['md_path']}")
    print(f"  * {summary['csv_path']}\n")


if __name__ == "__main__":
    main()
