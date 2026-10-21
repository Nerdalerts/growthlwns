import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import duckdb
import pandas as pd
from pydantic import BaseModel, Field

DEFAULT_DB_PATH = Path("data") / "olist.duckdb"

SKILL_NAME = "movement_explainer"
SKILL_DESCRIPTION = (
    "Decomposes metric changes between two time periods deterministically into volume effect, "
    "rate/AOV effect, and dimension contributions (by category, state, payment channel)."
)


class MovementExplainerInput(BaseModel):
    metric: str = "gmv"
    period_1_start: str = "2017-09-01"
    period_1_end: str = "2017-10-01"
    period_2_start: str = "2017-10-01"
    period_2_end: str = "2017-11-01"


class DimensionContribution(BaseModel):
    dimension_name: str
    dimension_value: str
    val_period_1: float
    val_period_2: float
    delta: float
    percent_contribution: float


class MovementDecomposition(BaseModel):
    metric: str
    period_1: str
    period_2: str
    val_1: float
    val_2: float
    total_delta: float
    total_delta_pct: float
    volume_effect: float
    rate_effect: float
    top_positive_categories: List[Dict[str, Any]]
    top_negative_categories: List[Dict[str, Any]]
    top_positive_states: List[Dict[str, Any]]
    narrative: str


def decompose_gmv_movement(
    p1_start: str,
    p1_end: str,
    p2_start: str,
    p2_end: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> MovementDecomposition:
    con = duckdb.connect(str(db_path), read_only=True)

    try:
        # 1. Total GMV and Order volume per period
        q_totals = f"""
            WITH p1 AS (
                SELECT 
                    COUNT(DISTINCT o.order_id) AS orders,
                    COALESCE(SUM(oi.price), 0.0) AS gmv
                FROM orders o JOIN order_items oi ON o.order_id = oi.order_id
                WHERE o.order_status = 'delivered'
                  AND o.order_purchase_timestamp >= '{p1_start}' AND o.order_purchase_timestamp < '{p1_end}'
            ),
            p2 AS (
                SELECT 
                    COUNT(DISTINCT o.order_id) AS orders,
                    COALESCE(SUM(oi.price), 0.0) AS gmv
                FROM orders o JOIN order_items oi ON o.order_id = oi.order_id
                WHERE o.order_status = 'delivered'
                  AND o.order_purchase_timestamp >= '{p2_start}' AND o.order_purchase_timestamp < '{p2_end}'
            )
            SELECT 
                p1.orders AS o1, p1.gmv AS g1,
                p2.orders AS o2, p2.gmv AS g2
            FROM p1, p2
        """
        row = con.execute(q_totals).fetchone()
        o1, g1, o2, g2 = (
            int(row[0] or 0),
            float(row[1] or 0.0),
            int(row[2] or 0),
            float(row[3] or 0.0),
        )

        aov1 = (g1 / o1) if o1 > 0 else 0.0
        aov2 = (g2 / o2) if o2 > 0 else 0.0

        total_delta = g2 - g1
        total_delta_pct = (total_delta / g1 * 100.0) if g1 > 0 else 0.0

        # Exact mathematical decomposition: Delta = Volume Effect + Rate/AOV Effect
        volume_effect = (o2 - o1) * aov1
        rate_effect = o2 * (aov2 - aov1)

        # 2. Category dimension decomposition
        q_cats = f"""
            WITH c1 AS (
                SELECT 
                    COALESCE(t.product_category_name_english, p.product_category_name, 'Other') AS cat,
                    COALESCE(SUM(oi.price), 0.0) AS gmv1
                FROM orders o
                JOIN order_items oi ON o.order_id = oi.order_id
                JOIN products p ON oi.product_id = p.product_id
                LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
                WHERE o.order_status = 'delivered'
                  AND o.order_purchase_timestamp >= '{p1_start}' AND o.order_purchase_timestamp < '{p1_end}'
                GROUP BY 1
            ),
            c2 AS (
                SELECT 
                    COALESCE(t.product_category_name_english, p.product_category_name, 'Other') AS cat,
                    COALESCE(SUM(oi.price), 0.0) AS gmv2
                FROM orders o
                JOIN order_items oi ON o.order_id = oi.order_id
                JOIN products p ON oi.product_id = p.product_id
                LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
                WHERE o.order_status = 'delivered'
                  AND o.order_purchase_timestamp >= '{p2_start}' AND o.order_purchase_timestamp < '{p2_end}'
                GROUP BY 1
            )
            SELECT 
                COALESCE(c1.cat, c2.cat) AS cat,
                COALESCE(gmv1, 0.0) AS gmv1,
                COALESCE(gmv2, 0.0) AS gmv2,
                (COALESCE(gmv2, 0.0) - COALESCE(gmv1, 0.0)) AS delta
            FROM c1 FULL OUTER JOIN c2 ON c1.cat = c2.cat
            ORDER BY delta DESC
        """
        cat_df = con.execute(q_cats).df()

        # 3. Customer State dimension decomposition
        q_states = f"""
            WITH s1 AS (
                SELECT c.customer_state AS st, COALESCE(SUM(oi.price), 0.0) AS gmv1
                FROM orders o
                JOIN order_items oi ON o.order_id = oi.order_id
                JOIN customers c ON o.customer_id = c.customer_id
                WHERE o.order_status = 'delivered'
                  AND o.order_purchase_timestamp >= '{p1_start}' AND o.order_purchase_timestamp < '{p1_end}'
                GROUP BY 1
            ),
            s2 AS (
                SELECT c.customer_state AS st, COALESCE(SUM(oi.price), 0.0) AS gmv2
                FROM orders o
                JOIN order_items oi ON o.order_id = oi.order_id
                JOIN customers c ON o.customer_id = c.customer_id
                WHERE o.order_status = 'delivered'
                  AND o.order_purchase_timestamp >= '{p2_start}' AND o.order_purchase_timestamp < '{p2_end}'
                GROUP BY 1
            )
            SELECT 
                COALESCE(s1.st, s2.st) AS state,
                COALESCE(gmv1, 0.0) AS gmv1,
                COALESCE(gmv2, 0.0) AS gmv2,
                (COALESCE(gmv2, 0.0) - COALESCE(gmv1, 0.0)) AS delta
            FROM s1 FULL OUTER JOIN s2 ON s1.st = s2.st
            ORDER BY delta DESC
        """
        state_df = con.execute(q_states).df()

    finally:
        con.close()

    # Rank top category contributors
    top_pos_cats = cat_df[cat_df["delta"] > 0].head(3).to_dict(orient="records")
    top_neg_cats = (
        cat_df[cat_df["delta"] < 0].sort_values("delta").head(3).to_dict(orient="records")
    )
    top_pos_states = state_df.head(3).to_dict(orient="records")

    top_cat_names = ", ".join([f"{c['cat']} (+${c['delta']:,.0f})" for c in top_pos_cats])

    narrative = (
        f"GMV changed by ${total_delta:+,.2f} ({total_delta_pct:+.1f}%) from ${g1:,.2f} to ${g2:,.2f}. "
        f"Volume effect contributed ${volume_effect:+,.2f} ({o2 - o1:+d} orders), while AOV effect contributed ${rate_effect:+,.2f} "
        f"(${aov2 - aov1:+.2f}/order). Top positive drivers were {top_cat_names}."
    )

    return MovementDecomposition(
        metric="gmv",
        period_1=f"{p1_start} to {p1_end}",
        period_2=f"{p2_start} to {p2_end}",
        val_1=g1,
        val_2=g2,
        total_delta=total_delta,
        total_delta_pct=total_delta_pct,
        volume_effect=volume_effect,
        rate_effect=rate_effect,
        top_positive_categories=top_pos_cats,
        top_negative_categories=top_neg_cats,
        top_positive_states=top_pos_states,
        narrative=narrative,
    )


def run(**kwargs) -> Dict[str, Any]:
    p = MovementExplainerInput(**kwargs)
    result = decompose_gmv_movement(
        p.period_1_start,
        p.period_1_end,
        p.period_2_start,
        p.period_2_end,
    )
    return result.model_dump()
