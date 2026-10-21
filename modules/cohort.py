import streamlit as st
import plotly.graph_objects as go
import numpy as np
from data.loader import get_cohort


def _t():
    return {
        "plot_bg": st.session_state.get("_plot_bg", "#ffffff"),
        "paper":   st.session_state.get("_plot_paper", "#ffffff"),
        "grid":    st.session_state.get("_grid", "#f0f0f0"),
        "text":    st.session_state.get("_text", "#111"),
        "bar":     st.session_state.get("_bar_color", "#3b82f6"),
    }


def render():
    st.markdown('<p class="page-title">Cohort Retention</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-subtitle">Monthly repurchase retention by acquisition cohort · how well are you keeping buyers?</p>',
        unsafe_allow_html=True,
    )

    df = get_cohort()
    t  = _t()

    pivot = df.pivot(index="cohort", columns="week", values="retention")
    pivot.columns = [f"Month +{w}" for w in pivot.columns]

    w1_avg = df[df["week"] == 1]["retention"].mean() if 1 in df["week"].values else 0
    w4_avg = df[df["week"] == 4]["retention"].mean() if 4 in df["week"].values else 0
    w8_avg = df[df["week"] == 8]["retention"].mean() if 8 in df["week"].values else 0
    col_4  = "Month +4" if "Month +4" in pivot.columns else pivot.columns[-1]
    best_c = pivot[col_4].idxmax()

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("M+1 Retention",    f"{w1_avg*100:.1f}%", help="Avg across all cohorts")
    with c2: st.metric("M+4 Retention",    f"{w4_avg*100:.1f}%")
    with c3: st.metric("M+8 Retention",    f"{w8_avg*100:.1f}%")
    with c4: st.metric("Best Cohort (M+4)", best_c)

    st.markdown(
        '<p class="section-label">Retention heatmap · % of cohort who repurchased</p>',
        unsafe_allow_html=True,
    )

    z_vals   = pivot.values * 100
    x_labels = list(pivot.columns)
    y_labels = list(pivot.index)
    text_vals = [[f"{v:.0f}%" if not np.isnan(v) else "" for v in row] for row in z_vals]

    fig = go.Figure(go.Heatmap(
        z=z_vals, x=x_labels, y=y_labels,
        text=text_vals, texttemplate="%{text}",
        textfont=dict(size=11, family="DM Mono"),
        colorscale=[
            [0.0, "#eff6ff"], [0.3, "#bfdbfe"],
            [0.6, "#3b82f6"], [1.0, "#1e3a8a"],
        ],
        showscale=True,
        colorbar=dict(ticksuffix="%", thickness=12, len=0.8,
                      tickfont=dict(color=t["text"])),
        zmin=0, zmax=100,
    ))
    fig.update_layout(
        height=380, margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor=t["paper"],
        font=dict(family="DM Sans", size=12, color=t["text"]),
        xaxis=dict(side="top", tickfont=dict(color=t["text"])),
        yaxis=dict(tickfont=dict(color=t["text"])),
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown(
        '<p class="section-label">Average retention curve · all cohorts</p>',
        unsafe_allow_html=True,
    )
    avg_curve = df.groupby("week")["retention"].mean().reset_index()

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=avg_curve["week"], y=avg_curve["retention"] * 100,
        mode="lines+markers",
        line=dict(color=t["bar"], width=2.5), marker=dict(size=7, color=t["bar"]),
        fill="tozeroy", fillcolor="rgba(59,130,246,0.07)",
        name="Avg retention",
    ))
    benchmark = [100, 28, 15, 11, 9, 8, 7, 7, 6, 6, 5, 5]
    fig2.add_trace(go.Scatter(
        x=list(range(len(benchmark))), y=benchmark, mode="lines",
        line=dict(color="#f59e0b", width=1.5, dash="dash"),
        name="E-commerce benchmark",
    ))
    fig2.update_layout(
        height=260, margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor=t["plot_bg"], paper_bgcolor=t["paper"],
        font=dict(family="DM Sans", size=12, color=t["text"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    font=dict(color=t["text"])),
        xaxis=dict(title="Months since first purchase", showgrid=False, dtick=1,
                   tickfont=dict(color=t["text"]), title_font=dict(color=t["text"])),
        yaxis=dict(title="Retention %", gridcolor=t["grid"], ticksuffix="%",
                   tickfont=dict(color=t["text"]), title_font=dict(color=t["text"])),
    )
    st.plotly_chart(fig2, width="stretch")

    st.markdown('<p class="section-label">Cohort sizes</p>', unsafe_allow_html=True)
    sizes = df[df["week"] == 0][["cohort","cohort_size"]].copy()
    sizes.columns = ["Cohort", "New Buyers"]
    sizes["New Buyers"] = sizes["New Buyers"].apply(lambda x: f"{x:,}")
    st.dataframe(sizes, width="stretch", hide_index=True)

    st.markdown(
        '<div class="insight-box">📌 <strong>PM Insight:</strong> '
        "Month 0 → Month 1 drop is the steepest. "
        "A post-purchase email at Day 7–10 with a personalised reorder nudge can lift M+1 retention by 10–15%. "
        "Q4 cohorts typically show higher LTV due to gift-buying patterns.</div>",
        unsafe_allow_html=True,
    )
