from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pydantic import BaseModel, ConfigDict, Field

from copilot.llm import LLMClient, LLMResult
from copilot.logging_db import log_call
from copilot.metrics import format_metrics_for_prompt, load_metrics
from copilot.sql_guard import SQLGuardError, validate_and_sanitize_sql

DEFAULT_DB_PATH = Path("data") / "olist.duckdb"
PROMPT_V1_PATH = Path("prompts") / "sql_v1.md"


class LLMQueryResponse(BaseModel):
    sql: Optional[str] = None
    metric_used: str = "none"
    assumptions: Optional[str] = None
    refusal_reason: Optional[str] = None
    chart_type: str = "table"
    narrative: Optional[str] = None


class MetricQAResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    question: str
    sql: Optional[str] = None
    sanitized_sql: Optional[str] = None
    metric_used: Optional[str] = None
    assumptions: Optional[str] = None
    refusal_reason: Optional[str] = None
    narrative: Optional[str] = None
    chart_type: str = "table"
    data: Optional[List[Dict[str, Any]]] = None
    df: Optional[pd.DataFrame] = None
    success: bool = True
    error_type: Optional[str] = None
    log_id: Optional[int] = None
    latency_ms: int = 0
    metric_definition: Optional[Dict[str, Any]] = None


def check_narrative_numbers(narrative: str, df: pd.DataFrame) -> bool:
    """Validate that every significant number in the narrative exists in the DataFrame."""
    if not narrative or df.empty:
        return True

    # Flatten all dataframe values to strings
    df_values: set[str] = set()
    for col in df.columns:
        df_values.add(str(col).lower())
        for val in df[col].dropna():
            # Add formatted variants
            df_values.add(str(val).lower())
            if isinstance(val, (int, float)):
                df_values.add(f"{val:.2f}")
                df_values.add(f"{val:.1f}")
                df_values.add(f"{val:,.2f}")
                df_values.add(f"{val:,.0f}")
                df_values.add(str(int(val)))
            elif hasattr(val, "strftime"):
                df_values.add(val.strftime("%Y-%m"))
                df_values.add(val.strftime("%Y"))
                df_values.add(str(val.year))
                df_values.add(str(val.month))

    combined_df_text = " ".join(df_values)

    # Extract all numeric tokens from narrative (strip commas and currencies)
    clean_narrative = re.sub(r"[\$,%]", "", narrative)
    tokens = re.findall(r"\b\d+(?:\.\d+)?\b", clean_narrative)

    for token in tokens:
        # Allow trivial grammatical numbers (1, 2) if narrative mentions "top 2" or "1 month"
        if token in ("1", "2"):
            continue
        # Check if number or int part appears in dataframe
        if token not in combined_df_text and token.split(".")[0] not in combined_df_text:
            return False

    return True


def build_system_prompt(prompt_path: Path = PROMPT_V1_PATH) -> str:
    base_prompt = ""
    if prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            base_prompt = f.read()

    metrics_guide = format_metrics_for_prompt()
    return f"{base_prompt}\n\n{metrics_guide}"


def generate_auto_chart(df: pd.DataFrame, chart_type: str = "table") -> Optional[go.Figure]:
    if df is None or df.empty or len(df.columns) < 2:
        return None

    cols = list(df.columns)
    first_col, second_col = cols[0], cols[1]

    # Detect if first column is temporal or categorical
    is_date = (
        pd.api.types.is_datetime64_any_dtype(df[first_col])
        or "month" in first_col.lower()
        or "date" in first_col.lower()
        or "year" in first_col.lower()
    )
    is_numeric_second = pd.api.types.is_numeric_dtype(df[second_col])

    try:
        if chart_type == "line" or (is_date and is_numeric_second):
            fig = px.line(
                df,
                x=first_col,
                y=second_col,
                markers=True,
                title=f"{second_col} over {first_col}",
            )
            fig.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20))
            return fig
        elif chart_type == "pie" and len(df) <= 10 and is_numeric_second:
            fig = px.pie(
                df,
                names=first_col,
                values=second_col,
                hole=0.4,
                title=f"{second_col} distribution by {first_col}",
            )
            fig.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20))
            return fig
        elif is_numeric_second:
            fig = px.bar(
                df,
                x=first_col,
                y=second_col,
                title=f"{second_col} by {first_col}",
            )
            fig.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20))
            return fig
    except Exception:
        return None

    return None


def run_metric_qa(
    question: str,
    session_id: str = "default_session",
    db_path: Path = DEFAULT_DB_PATH,
    llm_client: Optional[LLMClient] = None,
    system_prompt_path: Path = PROMPT_V1_PATH,
) -> MetricQAResult:
    start_time = time.time()
    client = llm_client or LLMClient()
    system_prompt = build_system_prompt(system_prompt_path)

    # 1. Scope check & LLM generation
    llm_res: LLMResult
    try:
        llm_res = client.call_structured(
            prompt=f"Question: {question}",
            system_prompt=system_prompt,
            response_model=LLMQueryResponse,
        )
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        log_id = log_call(
            session_id=session_id,
            skill="metric_qa",
            question=question,
            generated_sql=None,
            success=False,
            error_type="llm_generation_error",
            latency_ms=latency,
        )
        return MetricQAResult(
            question=question,
            success=False,
            error_type="llm_generation_error",
            refusal_reason=str(e),
            log_id=log_id,
            latency_ms=latency,
        )

    response_data: LLMQueryResponse = llm_res.data

    # 2. Check for refusal
    if response_data.refusal_reason or not response_data.sql:
        latency = int((time.time() - start_time) * 1000)
        log_id = log_call(
            session_id=session_id,
            skill="metric_qa",
            question=question,
            generated_sql=None,
            success=True,
            error_type="refusal",
            latency_ms=latency,
            input_tokens=llm_res.input_tokens,
            output_tokens=llm_res.output_tokens,
        )
        return MetricQAResult(
            question=question,
            refusal_reason=response_data.refusal_reason
            or "This question cannot be answered from the Olist dataset.",
            success=True,
            error_type="refusal",
            log_id=log_id,
            latency_ms=latency,
        )

    # 3. SQL Guard validation
    sanitized_sql: str
    try:
        sanitized_sql = validate_and_sanitize_sql(response_data.sql)
    except SQLGuardError as guard_err:
        latency = int((time.time() - start_time) * 1000)
        log_id = log_call(
            session_id=session_id,
            skill="metric_qa",
            question=question,
            generated_sql=response_data.sql,
            success=False,
            error_type="sql_guard_violation",
            latency_ms=latency,
            input_tokens=llm_res.input_tokens,
            output_tokens=llm_res.output_tokens,
        )
        return MetricQAResult(
            question=question,
            sql=response_data.sql,
            success=False,
            error_type="sql_guard_violation",
            refusal_reason=f"Security guardrail rejected query: {guard_err}",
            log_id=log_id,
            latency_ms=latency,
        )

    # 4. Execute SQL against DuckDB with single automatic retry on query error
    df: Optional[pd.DataFrame] = None
    con = duckdb.connect(str(db_path), read_only=True)
    execution_error: Optional[str] = None

    try:
        con.execute("SET statement_timeout = '10000ms'")
        df = con.execute(sanitized_sql).df()
    except Exception as db_err:
        execution_error = str(db_err)
        # Attempt single retry with error feedback
        retry_prompt = (
            f"Question: {question}\n\n"
            f"The SQL query you generated:\n{sanitized_sql}\n"
            f"Failed with DuckDB error:\n{execution_error}\n\n"
            "Please fix the SQL query and return updated JSON."
        )
        try:
            retry_res = client.call_structured(
                prompt=retry_prompt,
                system_prompt=system_prompt,
                response_model=LLMQueryResponse,
            )
            response_data = retry_res.data
            if response_data.sql:
                sanitized_sql = validate_and_sanitize_sql(response_data.sql)
                df = con.execute(sanitized_sql).df()
                execution_error = None
        except Exception as retry_err:
            execution_error = f"{execution_error} | Retry failed: {str(retry_err)}"
    finally:
        con.close()

    if execution_error or df is None:
        latency = int((time.time() - start_time) * 1000)
        log_id = log_call(
            session_id=session_id,
            skill="metric_qa",
            question=question,
            generated_sql=sanitized_sql,
            success=False,
            error_type="sql_execution_error",
            latency_ms=latency,
            input_tokens=llm_res.input_tokens,
            output_tokens=llm_res.output_tokens,
        )
        return MetricQAResult(
            question=question,
            sql=response_data.sql,
            sanitized_sql=sanitized_sql,
            success=False,
            error_type="sql_execution_error",
            refusal_reason=f"Database execution error: {execution_error}",
            log_id=log_id,
            latency_ms=latency,
        )

    # 5. Narrative number check
    narrative = response_data.narrative
    error_type = None
    if narrative:
        is_consistent = check_narrative_numbers(narrative, df)
        if not is_consistent:
            narrative = None
            error_type = "narrative_mismatch"

    # 6. Retrieve metric definition if known
    metric_def = None
    try:
        all_metrics = load_metrics()
        metric_key = (response_data.metric_used or "").lower()
        if metric_key in all_metrics:
            metric_def = all_metrics[metric_key].model_dump()
    except Exception:
        pass

    latency = int((time.time() - start_time) * 1000)
    log_id = log_call(
        session_id=session_id,
        skill="metric_qa",
        question=question,
        generated_sql=sanitized_sql,
        success=True,
        error_type=error_type,
        latency_ms=latency,
        input_tokens=llm_res.input_tokens,
        output_tokens=llm_res.output_tokens,
    )

    return MetricQAResult(
        question=question,
        sql=response_data.sql,
        sanitized_sql=sanitized_sql,
        metric_used=response_data.metric_used,
        assumptions=response_data.assumptions,
        refusal_reason=None,
        narrative=narrative,
        chart_type=response_data.chart_type,
        data=df.to_dict(orient="records"),
        df=df,
        success=True,
        error_type=error_type,
        log_id=log_id,
        latency_ms=latency,
        metric_definition=metric_def,
    )
