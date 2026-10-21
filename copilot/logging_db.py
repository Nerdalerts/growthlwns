from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
import pandas as pd

DEFAULT_LOG_DB_PATH = Path("logs") / "usage.db"


def get_log_db_path() -> Path:
    db_path = DEFAULT_LOG_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def init_db(db_path: Optional[Path] = None) -> None:
    path = db_path or get_log_db_path()
    with sqlite3.connect(str(path)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT,
                skill TEXT,
                question TEXT,
                generated_sql TEXT,
                success INTEGER,
                error_type TEXT,
                latency_ms INTEGER,
                input_tokens INTEGER,
                output_tokens INTEGER,
                thumbs TEXT,
                user_comment TEXT
            )
        """)
        conn.commit()


def log_call(
    session_id: str,
    skill: str,
    question: str,
    generated_sql: Optional[str],
    success: bool,
    error_type: Optional[str] = None,
    latency_ms: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    db_path: Optional[Path] = None,
) -> int:
    path = db_path or get_log_db_path()
    init_db(path)
    with sqlite3.connect(str(path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO usage_log (
                ts, session_id, skill, question, generated_sql,
                success, error_type, latency_ms, input_tokens, output_tokens
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                session_id,
                skill,
                question,
                generated_sql,
                1 if success else 0,
                error_type,
                latency_ms,
                input_tokens,
                output_tokens,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def update_feedback(
    log_id: int,
    thumbs: str,
    user_comment: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> None:
    path = db_path or get_log_db_path()
    init_db(path)
    with sqlite3.connect(str(path)) as conn:
        conn.execute(
            """
            UPDATE usage_log
            SET thumbs = ?, user_comment = COALESCE(?, user_comment)
            WHERE id = ?
            """,
            (thumbs, user_comment, log_id),
        )
        conn.commit()


def get_usage_dataframe(db_path: Optional[Path] = None) -> pd.DataFrame:
    path = db_path or get_log_db_path()
    init_db(path)
    with sqlite3.connect(str(path)) as conn:
        return pd.read_sql_query("SELECT * FROM usage_log ORDER BY id DESC", conn)


def get_admin_metrics(db_path: Optional[Path] = None) -> Dict[str, Any]:
    df = get_usage_dataframe(db_path)
    if df.empty:
        return {
            "total_questions": 0,
            "distinct_sessions": 0,
            "success_rate": 0.0,
            "thumbs_up_rate": 0.0,
            "p50_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "top_failures": {},
        }

    total_questions = len(df)
    distinct_sessions = df["session_id"].nunique()
    success_rate = round(float(df["success"].mean() * 100), 1)

    rated = df[df["thumbs"].isin(["up", "down"])]
    thumbs_up_rate = (
        round(float((rated["thumbs"] == "up").mean() * 100), 1)
        if not rated.empty
        else 0.0
    )

    latencies = df["latency_ms"].dropna()
    p50_latency = float(latencies.quantile(0.50)) if not latencies.empty else 0.0
    p95_latency = float(latencies.quantile(0.95)) if not latencies.empty else 0.0

    failures = df[df["success"] == 0]
    top_failures = (
        failures["error_type"].value_counts().to_dict() if not failures.empty else {}
    )

    return {
        "total_questions": total_questions,
        "distinct_sessions": distinct_sessions,
        "success_rate": success_rate,
        "thumbs_up_rate": thumbs_up_rate,
        "p50_latency_ms": p50_latency,
        "p95_latency_ms": p95_latency,
        "top_failures": top_failures,
    }
