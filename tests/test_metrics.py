from pathlib import Path
import pytest
from copilot.metrics import (
    compute_metric,
    format_metrics_for_prompt,
    load_metrics,
)

METRICS_PATH = Path("metrics.yaml")
DB_PATH = Path("data") / "olist.duckdb"


def test_metrics_yaml_schema_and_required_keys():
    metrics = load_metrics(METRICS_PATH)
    required_keys = [
        "gmv",
        "order_count",
        "aov",
        "delivered_order_rate",
        "avg_review_score",
        "repeat_customer_rate",
        "on_time_delivery_rate",
    ]
    for key in required_keys:
        assert key in metrics, f"Missing required metric: {key}"
        m = metrics[key]
        assert len(m.name) > 0
        assert len(m.description) > 0
        assert len(m.sql_expression) > 0
        assert m.grain in ("order", "customer")
        assert len(m.known_pitfalls) > 0


@pytest.mark.skipif(not DB_PATH.exists(), reason="olist.duckdb not built")
def test_hand_checked_metrics_october_2017():
    """Verify computed metrics against hand-verified golden values for 2017-10."""
    gmv = compute_metric("gmv", 2017, 10, db_path=DB_PATH)
    assert pytest.approx(gmv, rel=1e-3) == 648247.65

    orders = compute_metric("order_count", 2017, 10, db_path=DB_PATH)
    assert orders == 4478

    aov = compute_metric("aov", 2017, 10, db_path=DB_PATH)
    assert pytest.approx(aov, rel=1e-3) == 144.76

    deliv_rate = compute_metric("delivered_order_rate", 2017, 10, db_path=DB_PATH)
    assert pytest.approx(deliv_rate, abs=1e-3) == 0.9670

    avg_review = compute_metric("avg_review_score", 2017, 10, db_path=DB_PATH)
    assert pytest.approx(avg_review, abs=1e-3) == 4.2052

    on_time = compute_metric("on_time_delivery_rate", 2017, 10, db_path=DB_PATH)
    assert pytest.approx(on_time, abs=1e-3) == 0.9471

    repeat_rate = compute_metric("repeat_customer_rate", 2017, 10, db_path=DB_PATH)
    assert pytest.approx(repeat_rate, abs=1e-3) == 0.0136


def test_format_metrics_for_prompt():
    prompt_text = format_metrics_for_prompt(METRICS_PATH)
    assert "CANONICAL METRIC DEFINITIONS" in prompt_text
    assert "Gross Merchandise Value (GMV)" in prompt_text
    assert "Cartesian fan-out" in prompt_text
    assert "order_status = 'delivered'" in prompt_text
