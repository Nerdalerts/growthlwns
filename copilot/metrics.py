from pathlib import Path
from typing import Any, Dict, List, Optional
import duckdb
from pydantic import BaseModel, Field
import yaml

DEFAULT_METRICS_PATH = Path("metrics.yaml")
DEFAULT_DB_PATH = Path("data") / "olist.duckdb"


class MetricDefinition(BaseModel):
    name: str
    description: str
    sql_expression: str
    grain: str
    filters: List[str] = Field(default_factory=list)
    tables: List[str] = Field(default_factory=list)
    joins: List[str] = Field(default_factory=list)
    known_pitfalls: List[str] = Field(default_factory=list)


def load_metrics(metrics_path: Path | str = DEFAULT_METRICS_PATH) -> Dict[str, MetricDefinition]:
    path = Path(metrics_path)
    if not path.exists():
        raise FileNotFoundError(f"Metrics definition file not found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    raw_metrics = data.get("metrics", {})
    return {key: MetricDefinition(**val) for key, val in raw_metrics.items()}


def get_metric_sql_for_month(metric_key: str, year: int, month: int) -> str:
    start_date = f"{year:04d}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1:04d}-01-01"
    else:
        end_date = f"{year:04d}-{month + 1:02d}-01"

    if metric_key == "gmv":
        return f"""
            SELECT ROUND(SUM(oi.price), 2) AS value
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.order_status = 'delivered'
              AND o.order_purchase_timestamp >= '{start_date}'
              AND o.order_purchase_timestamp < '{end_date}'
        """
    elif metric_key == "order_count":
        return f"""
            SELECT COUNT(DISTINCT o.order_id) AS value
            FROM orders o
            WHERE o.order_status = 'delivered'
              AND o.order_purchase_timestamp >= '{start_date}'
              AND o.order_purchase_timestamp < '{end_date}'
        """
    elif metric_key == "aov":
        return f"""
            SELECT ROUND(SUM(oi.price) / COUNT(DISTINCT o.order_id), 2) AS value
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.order_status = 'delivered'
              AND o.order_purchase_timestamp >= '{start_date}'
              AND o.order_purchase_timestamp < '{end_date}'
        """
    elif metric_key == "delivered_order_rate":
        return f"""
            SELECT ROUND(
                COUNT(*) FILTER (WHERE order_status = 'delivered')::DOUBLE / COUNT(*),
                4
            ) AS value
            FROM orders
            WHERE order_purchase_timestamp >= '{start_date}'
              AND order_purchase_timestamp < '{end_date}'
        """
    elif metric_key == "avg_review_score":
        return f"""
            SELECT ROUND(AVG(r.review_score), 4) AS value
            FROM order_reviews r
            JOIN orders o ON r.order_id = o.order_id
            WHERE o.order_status = 'delivered'
              AND o.order_purchase_timestamp >= '{start_date}'
              AND o.order_purchase_timestamp < '{end_date}'
        """
    elif metric_key == "repeat_customer_rate":
        return f"""
            WITH customer_orders AS (
                SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS order_cnt
                FROM customers c
                JOIN orders o ON c.customer_id = o.customer_id
                WHERE o.order_status = 'delivered'
                  AND o.order_purchase_timestamp >= '{start_date}'
                  AND o.order_purchase_timestamp < '{end_date}'
                GROUP BY c.customer_unique_id
            )
            SELECT ROUND(
                COUNT(*) FILTER (WHERE order_cnt > 1)::DOUBLE / NULLIF(COUNT(*), 0),
                4
            ) AS value
            FROM customer_orders
        """
    elif metric_key == "on_time_delivery_rate":
        return f"""
            SELECT ROUND(
                COUNT(*) FILTER (WHERE order_delivered_customer_date <= order_estimated_delivery_date)::DOUBLE /
                NULLIF(COUNT(*) FILTER (WHERE order_delivered_customer_date IS NOT NULL AND order_estimated_delivery_date IS NOT NULL), 0),
                4
            ) AS value
            FROM orders
            WHERE order_status = 'delivered'
              AND order_purchase_timestamp >= '{start_date}'
              AND order_purchase_timestamp < '{end_date}'
        """
    else:
        raise ValueError(f"Unknown metric key: {metric_key}")


def compute_metric(
    metric_key: str,
    year: int,
    month: int,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> Any:
    sql = get_metric_sql_for_month(metric_key, year, month)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        row = con.execute(sql).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def format_metrics_for_prompt(metrics_path: Path | str = DEFAULT_METRICS_PATH) -> str:
    metrics = load_metrics(metrics_path)
    lines = ["## CANONICAL METRIC DEFINITIONS (SINGLE SOURCE OF TRUTH)"]
    for key, m in metrics.items():
        lines.append(f"\n### {m.name} (`{key}`)")
        lines.append(f"- **Description**: {m.description}")
        lines.append(f"- **SQL Expression**: `{m.sql_expression}`")
        lines.append(f"- **Grain**: {m.grain}")
        if m.filters:
            lines.append(f"- **Required Filters**: {', '.join(m.filters)}")
        if m.tables:
            lines.append(f"- **Tables**: {', '.join(m.tables)}")
        if m.known_pitfalls:
            lines.append("- **Known Pitfalls**:")
            for p in m.known_pitfalls:
                lines.append(f"  * {p}")
    return "\n".join(lines)
