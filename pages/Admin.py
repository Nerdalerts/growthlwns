import streamlit as st
import pandas as pd
import plotly.express as px
from copilot.logging_db import get_admin_metrics, get_usage_dataframe


def render():
    st.markdown('<p class="page-title">📊 Copilot Admin & Quality Dashboard</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-subtitle">Live adoption metrics, execution success rates, and user feedback logs</p>',
        unsafe_allow_html=True,
    )

    metrics = get_admin_metrics()
    df = get_usage_dataframe()

    # KPI Top Row
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Questions", f"{metrics['total_questions']:,}")
    with c2:
        st.metric("Distinct Sessions", f"{metrics['distinct_sessions']:,}")
    with c3:
        st.metric("Success Rate", f"{metrics['success_rate']:.1f}%")
    with c4:
        st.metric("Thumbs-Up Rate", f"{metrics['thumbs_up_rate']:.1f}%")

    c5, c6 = st.columns(2)
    with c5:
        st.metric("p50 Latency", f"{metrics['p50_latency_ms']:.0f} ms")
    with c6:
        st.metric("p95 Latency", f"{metrics['p95_latency_ms']:.0f} ms")

    if not df.empty:
        # 1. Questions per day chart
        st.markdown('<p class="section-label">Questions by Day</p>', unsafe_allow_html=True)
        df["date"] = pd.to_datetime(df["ts"]).dt.date
        daily_counts = df.groupby("date").size().reset_index(name="questions")
        fig_daily = px.bar(
            daily_counts,
            x="date",
            y="questions",
            title="Question Volume by Day",
        )
        fig_daily.update_layout(height=280, margin=dict(l=20, r=20, t=35, b=20))
        st.plotly_chart(fig_daily, use_container_width=True)

        col_left, col_right = st.columns(2)

        # 2. Failure types breakdown
        with col_left:
            st.markdown('<p class="section-label">Failure Types Breakdown</p>', unsafe_allow_html=True)
            if metrics["top_failures"]:
                fail_df = pd.DataFrame(
                    list(metrics["top_failures"].items()),
                    columns=["Failure Type", "Count"],
                )
                fig_fail = px.pie(
                    fail_df,
                    names="Failure Type",
                    values="Count",
                    hole=0.4,
                )
                fig_fail.update_layout(height=280, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig_fail, use_container_width=True)
            else:
                st.info("No failure records logged yet.")

        # 3. Thumbs down feedback table
        with col_right:
            st.markdown('<p class="section-label">Thumbs-Down Review Queue</p>', unsafe_allow_html=True)
            thumbs_down_df = df[df["thumbs"] == "down"][
                ["ts", "question", "user_comment", "generated_sql"]
            ]
            if not thumbs_down_df.empty:
                st.dataframe(thumbs_down_df, use_container_width=True)
            else:
                st.info("No negative ratings logged.")

        # 4. Recent usage log
        st.markdown('<p class="section-label">Recent Activity Log (All Queries)</p>', unsafe_allow_html=True)
        display_df = df[
            [
                "id",
                "ts",
                "session_id",
                "question",
                "success",
                "error_type",
                "latency_ms",
                "thumbs",
            ]
        ]
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No queries have been logged yet. Use the Ask Copilot page to get started!")


if __name__ == "__main__":
    render()
