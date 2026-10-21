import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from data.generator import get_cohort
import theme

def render():
    st.markdown('<p class="page-title">Cohort Retention</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Weekly repurchase retention by acquisition cohort · how well are you keeping buyers?</p>', unsafe_allow_html=True)

    df = get_cohort()

    # Pivot for heatmap
    pivot = df.pivot(index="cohort", columns="week", values="retention")
    pivot.columns = [f"Week {w}" for w in pivot.columns]

    # --- KPIs ---
    w1_avg  = df[df["week"] == 1]["retention"].mean()
    w4_avg  = df[df["week"] == 4]["retention"].mean()
    w8_avg  = df[df["week"] == 8]["retention"].mean()
    best_c  = pivot["Week 4"].idxmax() if "Week 4" in pivot.columns else "—"

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Week 1 Retention", f"{w1_avg*100:.1f}%", help="Avg across all cohorts")
    with c2: st.metric("Week 4 Retention", f"{w4_avg*100:.1f}%")
    with c3: st.metric("Week 8 Retention", f"{w8_avg*100:.1f}%")
    with c4: st.metric("Best Cohort (W4)", best_c)

    st.markdown('<p class="section-label">Retention heatmap · % of cohort who repurchased</p>', unsafe_allow_html=True)

    z_vals  = pivot.values * 100  # percent
    x_labels = list(pivot.columns)
    y_labels = list(pivot.index)

    # Mask NaN for display
    text_vals = []
    for row in z_vals:
        text_vals.append([f"{v:.0f}%" if not np.isnan(v) else "" for v in row])

    fig = go.Figure(go.Heatmap(
        z=z_vals,
        x=x_labels,
        y=y_labels,
        text=text_vals,
        texttemplate="%{text}",
        textfont=dict(size=11, family="DM Mono"),
        colorscale=[
            [0.0, "#eff6ff"],
            [0.3, "#bfdbfe"],
            [0.6, "#3b82f6"],
            [1.0, "#1e3a8a"],
        ],
        showscale=True,
        colorbar=dict(ticksuffix="%", thickness=12, len=0.8),
        zmin=0, zmax=100,
    ))
    fig.update_layout(
        height=380, margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor=theme.plot_bg(),
        font=dict(family="DM Sans", size=12, color="black"),
        xaxis=dict(side="top"),
    )
    st.plotly_chart(fig, width='stretch')

    # Retention curve overlay
    st.markdown('<p class="section-label">Average retention curve · all cohorts</p>', unsafe_allow_html=True)

    avg_curve = df.groupby("week")["retention"].mean().reset_index()

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=avg_curve["week"], y=avg_curve["retention"] * 100,
        mode="lines+markers",
        line=dict(color="#3b82f6", width=2.5),
        marker=dict(size=7, color="#3b82f6"),
        fill="tozeroy", fillcolor="rgba(59,130,246,0.07)",
        name="Avg retention",
    ))

    # Benchmark line
    benchmark = [100, 38, 25, 20, 18, 16, 15, 14, 13, 12, 11, 10]
    fig2.add_trace(go.Scatter(
        x=list(range(len(benchmark))),
        y=benchmark,
        mode="lines",
        line=dict(color="#f59e0b", width=1.5, dash="dash"),
        name="Industry benchmark",
    ))

    fig2.update_layout(
        height=260, margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor=theme.plot_bg(), paper_bgcolor=theme.plot_bg(),
        font=dict(family="DM Sans", size=12, color="black"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis=dict(title="Week", showgrid=False, dtick=1),
        yaxis=dict(title="Retention %", gridcolor=theme.grid_color(), ticksuffix="%"),
    )
    st.plotly_chart(fig2, width='stretch')

    # Cohort sizes
    st.markdown('<p class="section-label">Cohort sizes</p>', unsafe_allow_html=True)
    sizes = df[df["week"] == 0][["cohort","cohort_size"]].copy()
    sizes.columns = ["Cohort", "New Buyers"]
    sizes["New Buyers"] = sizes["New Buyers"].apply(lambda x: f"{x:,}")
    st.dataframe(sizes, width='stretch', hide_index=True)

    st.markdown('<div class="insight-box">📌 <strong>PM Insight:</strong> Week 1 → Week 2 drop is the steepest (100% → ~42%). This is the critical re-engagement window. Consider a post-purchase email sequence at Day 7–10 with a personalised reorder nudge or complementary product recommendation. Cohorts acquired via Email show ~15% higher Week 4 retention.</div>', unsafe_allow_html=True)