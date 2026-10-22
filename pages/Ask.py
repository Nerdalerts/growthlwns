import uuid
import streamlit as st
import pandas as pd

from copilot.logging_db import update_feedback
from copilot.skills.metric_qa import generate_auto_chart, run_metric_qa


def render():
    if "copilot_session_id" not in st.session_state:
        st.session_state.copilot_session_id = str(uuid.uuid4())[:8]

    st.markdown('<p class="page-title">💬 Ask Copilot: Metric Q&A</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-subtitle">Natural-language analytics over Brazilian Olist e-commerce data · 100% SQL traceable · Zero hallucinated numbers</p>',
        unsafe_allow_html=True,
    )

    SAMPLE_QUESTIONS = [
        "What was monthly GMV in 2017?",
        "What was the AOV in October 2017?",
        "What is our overall on-time delivery rate?",
        "Which payment type is used the most by order volume?",
        "What was our Customer Acquisition Cost (CAC) in 2017?",
    ]

    st.markdown('<p class="section-label">Sample Questions</p>', unsafe_allow_html=True)
    cols = st.columns(len(SAMPLE_QUESTIONS))
    for i, sample in enumerate(SAMPLE_QUESTIONS):
        with cols[i]:
            if st.button(sample, key=f"sample_{i}", use_container_width=True):
                st.session_state["user_question"] = sample

    question = st.text_input(
        "Ask a business or metric question:",
        value=st.session_state.get("user_question", ""),
        key="main_question_input",
        placeholder="e.g. What was total GMV and average order value in 2017?",
    )

    ask_btn = st.button("Run Analysis →", type="primary", use_container_width=False)

    if (ask_btn or "last_result" in st.session_state) and question:
        if ask_btn or st.session_state.get("cached_q") != question:
            with st.spinner("Analyzing data and generating verified SQL with Gemini..."):
                result = run_metric_qa(
                    question=question,
                    session_id=st.session_state.get("copilot_session_id", "default_session"),
                )
                st.session_state.last_result = result
                st.session_state.cached_q = question
        else:
            result = st.session_state.last_result

        # Handle refusals or guardrail violations
        if result.refusal_reason and not result.df:
            st.warning(f"**Refusal Reason:** {result.refusal_reason}")
            if result.error_type == "sql_guard_violation":
                st.error("Query was blocked by the security AST guardrail.")
        elif result.success and result.df is not None:
            # 1. Grounded Narrative Answer
            if result.narrative:
                st.markdown(
                    f'<div class="insight-box success">💡 <strong>Answer:</strong> {result.narrative}</div>',
                    unsafe_allow_html=True,
                )
            elif result.error_type == "narrative_mismatch":
                st.info("Showing verified data table directly.")

            # 2. Metric Definition
            if result.metric_definition:
                m = result.metric_definition
                with st.expander(f"📖 Metric Definition: {m.get('name', 'Custom')}", expanded=False):
                    st.markdown(f"**Description:** {m.get('description', '')}")
                    st.markdown(f"**Canonical SQL:** `{m.get('sql_expression', '')}`")
                    st.markdown(f"**Grain:** `{m.get('grain', '')}`")
                    for p in m.get("known_pitfalls", []):
                        st.markdown(f"- {p}")

            # 3. Interactive Chart
            fig = generate_auto_chart(result.df, result.chart_type)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)

            # 4. Result Data Table
            st.markdown('<p class="section-label">Result Data Table</p>', unsafe_allow_html=True)
            st.dataframe(result.df, use_container_width=True)

            # 5. Collapsible SQL with AST validation metadata
            with st.expander("🔍 View Verified SQL Query", expanded=False):
                st.code(result.sanitized_sql or result.sql, language="sql")
                if result.assumptions:
                    st.caption(f"**Assumptions:** {result.assumptions}")
                st.caption(f"Latency: {result.latency_ms} ms | Engine: DuckDB 2.0 (Read-Only)")

            # 6. Observability & User Feedback
            st.markdown('<p class="section-label">Was this answer helpful?</p>', unsafe_allow_html=True)
            f_col1, f_col2, _ = st.columns([1, 1, 4])
            with f_col1:
                if st.button("👍 Helpful", key="thumb_up", use_container_width=True):
                    if result.log_id:
                        update_feedback(result.log_id, "up")
                        st.success("Feedback logged!")
            with f_col2:
                if st.button("👎 Inaccurate", key="thumb_down", use_container_width=True):
                    st.session_state.show_comment_box = True

            if st.session_state.get("show_comment_box"):
                comment = st.text_input("Tell us what went wrong (optional):", key="feedback_comment")
                if st.button("Submit Feedback", key="submit_comment"):
                    if result.log_id:
                        update_feedback(result.log_id, "down", comment)
                        st.info("Failure logged for prompt improvement evals.")
                        st.session_state.show_comment_box = False


if __name__ == "__main__":
    render()
