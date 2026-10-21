import pandas as pd
import pytest
from evals.run import compare_dataframes, diagnose_failure, load_golden_set


def test_load_golden_set():
    questions = load_golden_set()
    assert len(questions) >= 30
    categories = {q["category"] for q in questions}
    assert "simple_aggregate" in categories
    assert "join" in categories
    assert "time_series" in categories
    assert "ratio" in categories
    assert "refusal" in categories


def test_compare_dataframes_scalar_numbers():
    df1 = pd.DataFrame({"gmv": [648247.65]})
    df2 = pd.DataFrame({"total": [648247.650001]})
    matches, note = compare_dataframes(df1, df2)
    assert matches is True

    df3 = pd.DataFrame({"gmv": [500000.00]})
    matches2, note2 = compare_dataframes(df1, df3)
    assert matches2 is False


def test_compare_dataframes_multi_row():
    df1 = pd.DataFrame({"month": ["2017-01", "2017-02"], "gmv": [100.0, 200.0]})
    df2 = pd.DataFrame({"mo": ["2017-01", "2017-02"], "val": [100.0, 200.0]})
    matches, note = compare_dataframes(df1, df2)
    assert matches is True

    # Row count difference
    df3 = pd.DataFrame({"month": ["2017-01"], "gmv": [100.0]})
    matches3, note3 = compare_dataframes(df1, df3)
    assert matches3 is False


def test_diagnose_failure_taxonomy():
    item_refusal = {"should_refuse": True, "category": "refusal"}
    tax1 = diagnose_failure(item_refusal, "SELECT 1", None, "mismatch")
    assert tax1 == "should_have_refused"

    item_normal = {"should_refuse": False, "category": "ratio"}
    tax2 = diagnose_failure(item_normal, None, "I refuse", "refused")
    assert tax2 == "should_not_have_refused"

    item_fanout = {"should_refuse": False, "category": "join"}
    tax3 = diagnose_failure(
        item_fanout,
        "SELECT * FROM orders o JOIN order_items oi ON o.order_id = oi.order_id JOIN order_payments op ON o.order_id = op.order_id",
        None,
        "wrong numbers",
    )
    assert tax3 == "fan_out_double_count"
