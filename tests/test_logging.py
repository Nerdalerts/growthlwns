import sqlite3
from pathlib import Path
import pytest
from copilot.logging_db import (
    get_admin_metrics,
    get_usage_dataframe,
    log_call,
    update_feedback,
)


def test_logging_and_admin_metrics(tmp_path):
    log_db = tmp_path / "test_usage.db"

    # Log 3 calls: 2 successes, 1 failure
    id1 = log_call(
        session_id="sess_1",
        skill="metric_qa",
        question="What is GMV?",
        generated_sql="SELECT SUM(price) FROM order_items",
        success=True,
        latency_ms=120,
        input_tokens=150,
        output_tokens=60,
        db_path=log_db,
    )
    update_feedback(id1, "up", db_path=log_db)

    id2 = log_call(
        session_id="sess_1",
        skill="metric_qa",
        question="What is CAC?",
        generated_sql=None,
        success=True,
        error_type="refusal",
        latency_ms=80,
        input_tokens=100,
        output_tokens=40,
        db_path=log_db,
    )

    id3 = log_call(
        session_id="sess_2",
        skill="metric_qa",
        question="Bad injection query",
        generated_sql="DROP TABLE orders",
        success=False,
        error_type="sql_guard_violation",
        latency_ms=30,
        input_tokens=50,
        output_tokens=20,
        db_path=log_db,
    )
    update_feedback(id3, "down", user_comment="Blocked unsafe SQL", db_path=log_db)

    # Verify admin numbers match direct SQL count on the log DB
    with sqlite3.connect(str(log_db)) as conn:
        direct_total = conn.execute("SELECT COUNT(*) FROM usage_log").fetchone()[0]
        direct_sessions = conn.execute("SELECT COUNT(DISTINCT session_id) FROM usage_log").fetchone()[0]
        direct_success = conn.execute("SELECT AVG(success) * 100 FROM usage_log").fetchone()[0]
        direct_thumbs_up = conn.execute(
            "SELECT (100.0 * COUNT(*) FILTER (WHERE thumbs = 'up')) / COUNT(*) FILTER (WHERE thumbs IN ('up', 'down')) FROM usage_log"
        ).fetchone()[0]

    admin_metrics = get_admin_metrics(db_path=log_db)

    assert admin_metrics["total_questions"] == direct_total == 3
    assert admin_metrics["distinct_sessions"] == direct_sessions == 2
    assert pytest.approx(admin_metrics["success_rate"], rel=1e-2) == direct_success
    assert pytest.approx(admin_metrics["thumbs_up_rate"], rel=1e-2) == direct_thumbs_up
    assert "sql_guard_violation" in admin_metrics["top_failures"]
    assert admin_metrics["top_failures"]["sql_guard_violation"] == 1

    # Verify history persistence across new connections
    df = get_usage_dataframe(db_path=log_db)
    assert len(df) == 3
    down_rows = df[df["thumbs"] == "down"]
    assert len(down_rows) == 1
    assert down_rows.iloc[0]["user_comment"] == "Blocked unsafe SQL"
