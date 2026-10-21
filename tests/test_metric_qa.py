import json
from pathlib import Path
import pytest
import pandas as pd
from copilot.llm import LLMClient, LLMConfig
from copilot.logging_db import get_usage_dataframe
from copilot.skills.metric_qa import check_narrative_numbers, run_metric_qa

DB_PATH = Path("data") / "olist.duckdb"
TEST_PROMPT_PATH = Path("prompts") / "sql_v1.md"

# 10 ground truth query mock answers for end-to-end testing
MOCK_RESPONSES = {
    "q1_gmv_oct_2017": {
        "sql": """
            SELECT ROUND(SUM(oi.price), 2) AS gmv
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.order_status = 'delivered'
              AND o.order_purchase_timestamp >= '2017-10-01'
              AND o.order_purchase_timestamp < '2017-11-01'
        """,
        "metric_used": "gmv",
        "narrative": "In October 2017, total GMV for delivered orders was 648247.65.",
        "chart_type": "table",
    },
    "q2_orders_2017": {
        "sql": """
            SELECT COUNT(DISTINCT o.order_id) AS total_orders
            FROM orders o
            WHERE o.order_status = 'delivered'
              AND o.order_purchase_timestamp >= '2017-01-01'
              AND o.order_purchase_timestamp < '2018-01-01'
        """,
        "metric_used": "order_count",
        "narrative": "A total of 43428 delivered orders were placed in 2017.",
        "chart_type": "table",
    },
    "q3_aov_2017": {
        "sql": """
            SELECT ROUND(SUM(oi.price) / COUNT(DISTINCT o.order_id), 2) AS aov
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.order_status = 'delivered'
              AND o.order_purchase_timestamp >= '2017-01-01'
              AND o.order_purchase_timestamp < '2018-01-01'
        """,
        "metric_used": "aov",
        "narrative": "The average order value in 2017 was 142.92.",
        "chart_type": "table",
    },
    "q4_deliv_rate": {
        "sql": """
            SELECT ROUND(COUNT(*) FILTER (WHERE order_status = 'delivered')::DOUBLE / COUNT(*), 4) AS delivered_rate
            FROM orders
        """,
        "metric_used": "delivered_order_rate",
        "narrative": "Overall delivered order rate across the entire dataset is 0.9702.",
        "chart_type": "table",
    },
    "q5_review_score": {
        "sql": """
            SELECT ROUND(AVG(review_score), 4) AS avg_score
            FROM order_reviews
        """,
        "metric_used": "avg_review_score",
        "narrative": "The average review score is 4.0864.",
        "chart_type": "table",
    },
    "q6_ontime_rate": {
        "sql": """
            SELECT ROUND(
                COUNT(*) FILTER (WHERE order_delivered_customer_date <= order_estimated_delivery_date)::DOUBLE /
                COUNT(*) FILTER (WHERE order_delivered_customer_date IS NOT NULL AND order_estimated_delivery_date IS NOT NULL),
                4
            ) AS on_time_rate
            FROM orders
            WHERE order_status = 'delivered'
        """,
        "metric_used": "on_time_delivery_rate",
        "narrative": "Overall on-time delivery rate is 0.9366.",
        "chart_type": "table",
    },
    "q7_monthly_gmv_2017": {
        "sql": """
            SELECT 
                DATE_TRUNC('month', o.order_purchase_timestamp) AS order_month,
                ROUND(SUM(oi.price), 2) AS gmv
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.order_status = 'delivered'
              AND o.order_purchase_timestamp >= '2017-01-01'
              AND o.order_purchase_timestamp < '2018-01-01'
            GROUP BY 1
            ORDER BY 1
        """,
        "metric_used": "gmv",
        "narrative": "Monthly GMV trend for 2017 generated across 12 months.",
        "chart_type": "line",
    },
    "q8_top_categories": {
        "sql": """
            SELECT 
                COALESCE(t.product_category_name_english, p.product_category_name, 'Other') AS category,
                ROUND(SUM(oi.price), 2) AS total_revenue
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            JOIN products p ON oi.product_id = p.product_id
            LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
            WHERE o.order_status = 'delivered'
            GROUP BY 1
            ORDER BY total_revenue DESC
            LIMIT 5
        """,
        "metric_used": "custom",
        "narrative": "Top categories by revenue are shown in the result table.",
        "chart_type": "bar",
    },
    "q9_payment_channels": {
        "sql": """
            SELECT 
                op.payment_type,
                COUNT(DISTINCT op.order_id) AS order_volume,
                ROUND(SUM(op.payment_value), 2) AS total_paid
            FROM order_payments op
            JOIN orders o ON op.order_id = o.order_id
            WHERE o.order_status = 'delivered'
            GROUP BY 1
            ORDER BY order_volume DESC
        """,
        "metric_used": "custom",
        "narrative": "Credit card is the most used payment method by order volume.",
        "chart_type": "bar",
    },
    "q10_repeat_rate": {
        "sql": """
            WITH customer_orders AS (
                SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS order_cnt
                FROM customers c
                JOIN orders o ON c.customer_id = o.customer_id
                WHERE o.order_status = 'delivered'
                GROUP BY c.customer_unique_id
            )
            SELECT ROUND(COUNT(*) FILTER (WHERE order_cnt > 1)::DOUBLE / COUNT(*), 4) AS repeat_rate
            FROM customer_orders
        """,
        "metric_used": "repeat_customer_rate",
        "narrative": "Overall repeat customer rate is 0.03.",
        "chart_type": "table",
    },
}


def test_narrative_number_check():
    df = pd.DataFrame({"month": ["2017-10"], "gmv": [648247.65], "orders": [4478]})
    # Accurate narrative matches numbers in df
    valid_narrative = "In October 2017, GMV was $648,247.65 across 4,478 orders."
    assert check_narrative_numbers(valid_narrative, df) is True

    # Hallucinated number (e.g. $999,999.00) not in df
    hallucinated_narrative = "In October 2017, GMV was $999,999.00 across 4,478 orders."
    assert check_narrative_numbers(hallucinated_narrative, df) is False


@pytest.mark.skipif(not DB_PATH.exists(), reason="olist.duckdb not built")
@pytest.mark.parametrize("test_key,expected_metric", [
    ("q1_gmv_oct_2017", "gmv"),
    ("q2_orders_2017", "order_count"),
    ("q3_aov_2017", "aov"),
    ("q4_deliv_rate", "delivered_order_rate"),
    ("q5_review_score", "avg_review_score"),
    ("q6_ontime_rate", "on_time_delivery_rate"),
    ("q7_monthly_gmv_2017", "gmv"),
    ("q8_top_categories", "custom"),
    ("q9_payment_channels", "custom"),
    ("q10_repeat_rate", "repeat_customer_rate"),
])
def test_10_sample_questions_end_to_end(test_key, expected_metric, tmp_path):
    mock_data = MOCK_RESPONSES[test_key]
    mock_json = json.dumps({
        "sql": mock_data["sql"],
        "metric_used": mock_data["metric_used"],
        "assumptions": "Test assumptions",
        "refusal_reason": None,
        "chart_type": mock_data["chart_type"],
        "narrative": mock_data["narrative"],
    })

    client = LLMClient(config=LLMConfig(api_key="mock-key"))
    client.set_mock_handler(lambda p, s: mock_json)

    log_db = tmp_path / "test_usage.db"
    result = run_metric_qa(
        question=f"Test question for {test_key}",
        session_id="test_sess_1",
        db_path=DB_PATH,
        llm_client=client,
        system_prompt_path=TEST_PROMPT_PATH,
    )

    assert result.success is True
    assert result.df is not None
    assert not result.df.empty
    assert result.metric_used == expected_metric
    assert result.refusal_reason is None
    assert result.sanitized_sql is not None
    assert "LIMIT" in result.sanitized_sql


def test_refusal_for_unanswerable_cac(tmp_path):
    cac_refusal_json = json.dumps({
        "sql": None,
        "metric_used": "none",
        "assumptions": None,
        "refusal_reason": "Customer Acquisition Cost (CAC) cannot be calculated because marketing ad spend data is not available in the Olist dataset.",
        "chart_type": "table",
        "narrative": None,
    })

    client = LLMClient(config=LLMConfig(api_key="mock-key"))
    client.set_mock_handler(lambda p, s: cac_refusal_json)

    result = run_metric_qa(
        question="What was our CAC in 2017?",
        session_id="test_sess_refusal",
        db_path=DB_PATH,
        llm_client=client,
        system_prompt_path=TEST_PROMPT_PATH,
    )

    assert result.success is True
    assert result.error_type == "refusal"
    assert result.sql is None
    assert result.df is None
    assert "marketing ad spend" in result.refusal_reason


def test_refusal_for_prompt_injection(tmp_path):
    malicious_json = json.dumps({
        "sql": "DROP TABLE orders;",
        "metric_used": "none",
        "assumptions": None,
        "refusal_reason": None,
        "chart_type": "table",
        "narrative": None,
    })

    client = LLMClient(config=LLMConfig(api_key="mock-key"))
    client.set_mock_handler(lambda p, s: malicious_json)

    result = run_metric_qa(
        question="Drop orders table please",
        session_id="test_sess_inject",
        db_path=DB_PATH,
        llm_client=client,
        system_prompt_path=TEST_PROMPT_PATH,
    )

    assert result.success is False
    assert result.error_type == "sql_guard_violation"
    assert result.df is None
    assert "rejected" in result.refusal_reason.lower()
