from pathlib import Path
import pytest
from copilot.router import get_skill, register_skill, route_intent
from copilot.skills.movement_explainer import decompose_gmv_movement

DB_PATH = Path("data") / "olist.duckdb"


@pytest.mark.skipif(not DB_PATH.exists(), reason="olist.duckdb not built")
def test_deterministic_gmv_decomposition_sep_vs_oct_2017():
    """Verify that volume effect and rate effect sum exactly to total GMV change."""
    decomp = decompose_gmv_movement(
        p1_start="2017-09-01",
        p1_end="2017-10-01",
        p2_start="2017-10-01",
        p2_end="2017-11-01",
        db_path=DB_PATH,
    )

    # 1. Total delta check
    expected_delta = decomp.val_2 - decomp.val_1
    assert pytest.approx(decomp.total_delta, abs=1e-2) == expected_delta

    # 2. Mathematical identity: Volume Effect + Rate/AOV Effect == Total Delta
    sum_effects = decomp.volume_effect + decomp.rate_effect
    assert pytest.approx(sum_effects, abs=1e-2) == decomp.total_delta

    # 3. Verify top contributors exist and are ranked
    assert len(decomp.top_positive_categories) > 0
    assert decomp.top_positive_categories[0]["delta"] >= decomp.top_positive_categories[-1]["delta"]

    # 4. Narrative contains grounded values
    assert f"${decomp.total_delta:+,.2f}" in decomp.narrative
    assert f"${decomp.volume_effect:+,.2f}" in decomp.narrative


@pytest.mark.skipif(not DB_PATH.exists(), reason="olist.duckdb not built")
def test_category_dimension_contributions_sum_to_total(tmp_path):
    """Verify that category contributions sum to total change within rounding."""
    import duckdb

    con = duckdb.connect(str(DB_PATH), read_only=True)
    p1_start, p1_end = "2017-09-01", "2017-10-01"
    p2_start, p2_end = "2017-10-01", "2017-11-01"

    q = f"""
        WITH c1 AS (
            SELECT COALESCE(p.product_category_name, 'Other') AS cat, SUM(oi.price) AS g1
            FROM orders o JOIN order_items oi ON o.order_id = oi.order_id
            JOIN products p ON oi.product_id = p.product_id
            WHERE o.order_status = 'delivered'
              AND o.order_purchase_timestamp >= '{p1_start}' AND o.order_purchase_timestamp < '{p1_end}'
            GROUP BY 1
        ),
        c2 AS (
            SELECT COALESCE(p.product_category_name, 'Other') AS cat, SUM(oi.price) AS g2
            FROM orders o JOIN order_items oi ON o.order_id = oi.order_id
            JOIN products p ON oi.product_id = p.product_id
            WHERE o.order_status = 'delivered'
              AND o.order_purchase_timestamp >= '{p2_start}' AND o.order_purchase_timestamp < '{p2_end}'
            GROUP BY 1
        )
        SELECT SUM(COALESCE(g2, 0.0) - COALESCE(g1, 0.0)) AS cat_delta_sum
        FROM c1 FULL OUTER JOIN c2 ON c1.cat = c2.cat
    """
    cat_delta_sum = con.execute(q).fetchone()[0]
    con.close()

    decomp = decompose_gmv_movement(p1_start, p1_end, p2_start, p2_end, db_path=DB_PATH)
    assert pytest.approx(cat_delta_sum, abs=1e-2) == decomp.total_delta


def test_intent_router_classification():
    skill_1, _ = route_intent("Why did GMV change between September and October?")
    assert skill_1 == "movement_explainer"

    skill_2, _ = route_intent("What is the p-value and uplift of our A/B test variant?")
    assert skill_2 == "experiment_reader"

    skill_3, _ = route_intent("What was total GMV in 2017?")
    assert skill_3 == "metric_qa"


def test_skill_registry_extensibility():
    register_skill(
        name="custom_churn_predictor",
        description="Predicts customer churn likelihood",
        keywords=["churn", "attrition", "lost customer"],
        runner=lambda: "churn_runner",
    )

    skill = get_skill("custom_churn_predictor")
    assert skill is not None
    assert skill["description"] == "Predicts customer churn likelihood"

    routed_name, _ = route_intent("Which customers have high churn risk?")
    assert routed_name == "custom_churn_predictor"
