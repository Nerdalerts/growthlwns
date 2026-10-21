import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from data.loader import get_rfm

SEG_COLORS = {
    "Champions":           "#1d4ed8",
    "Loyal":               "#3b82f6",
    "Potential Loyalists": "#60a5fa",
    "New Customers":       "#22c55e",
    "At Risk":             "#f59e0b",
    "Lost":                "#ef4444",
}

SEG_ACTIONS = {
    "Champions":           "Reward & upsell. Enroll in loyalty programme, offer early access to new launches.",
    "Loyal":               "Increase frequency. Target with subscription offers or replenishment reminders.",
    "Potential Loyalists": "Nurture to Champions. Send personalised recommendations based on first purchase.",
    "New Customers":       "Activate the second purchase. Post-purchase email at Day 10 with 10% off.",
    "At Risk":             "Win-back urgently. Personalised 'we miss you' offer within 2 weeks.",
    "Lost":                "Low-cost reactivation or accept churn. One-time deep discount email before writing off.",
}


def _t():
    return {
        "plot_bg": st.session_state.get("_plot_bg", "#ffffff"),
        "paper":   st.session_state.get("_plot_paper", "#ffffff"),
        "grid":    st.session_state.get("_grid", "#f0f0f0"),
        "text":    st.session_state.get("_text", "#111"),
    }


def render():
    st.markdown('<p class="page-title">RFM Segmentation</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-subtitle">Recency · Frequency · Monetary — know exactly who your customers are and what to do next</p>',
        unsafe_allow_html=True,
    )

    rfm = get_rfm()
    t   = _t()

    champ_pct = (rfm["segment"] == "Champions").mean() * 100
    risk_pct  = (rfm["segment"] == "At Risk").mean() * 100
    lost_pct  = (rfm["segment"] == "Lost").mean() * 100
    avg_ltv   = rfm["monetary"].mean()

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Champions",        f"{champ_pct:.1f}%", help="% of customer base")
    with c2: st.metric("At Risk",          f"{risk_pct:.1f}%",
                        delta=f"-{risk_pct:.1f}% ideal", delta_color="inverse")
    with c3: st.metric("Lost",             f"{lost_pct:.1f}%", delta_color="inverse")
    with c4: st.metric("Avg Customer LTV", f"${avg_ltv:.0f}")

    col_l, col_r = st.columns([1.2, 1])

    with col_l:
        st.markdown('<p class="section-label">Segment distribution</p>', unsafe_allow_html=True)
        seg_counts = rfm["segment"].value_counts().reset_index()
        seg_counts.columns = ["segment", "count"]
        seg_counts["color"] = seg_counts["segment"].map(SEG_COLORS)
        seg_counts["pct"]   = (seg_counts["count"] / seg_counts["count"].sum() * 100).round(1)

        fig = go.Figure(go.Bar(
            x=seg_counts["count"], y=seg_counts["segment"],
            orientation="h", marker_color=seg_counts["color"],
            text=[f"{c:,}  ({p:.1f}%)" for c, p in zip(seg_counts["count"], seg_counts["pct"])],
            textposition="outside",
            textfont=dict(color=t["text"]),
        ))
        fig.update_layout(
            height=280, margin=dict(l=0, r=120, t=5, b=0),
            plot_bgcolor=t["plot_bg"], paper_bgcolor=t["paper"],
            font=dict(family="DM Sans", size=12, color=t["text"]),
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(showgrid=False, categoryorder="total ascending",
                       tickfont=dict(color=t["text"])),
        )
        st.plotly_chart(fig, width="stretch")

    with col_r:
        st.markdown('<p class="section-label">Revenue by segment</p>', unsafe_allow_html=True)
        seg_rev = rfm.groupby("segment")["monetary"].sum().reset_index()
        seg_rev["color"] = seg_rev["segment"].map(SEG_COLORS)
        fig2 = go.Figure(go.Pie(
            labels=seg_rev["segment"],
            values=seg_rev["monetary"].round(0),
            marker_colors=seg_rev["color"],
            hole=0.5, textinfo="label+percent", textfont_size=11,
        ))
        fig2.update_layout(
            height=280, margin=dict(l=0, r=0, t=5, b=0),
            paper_bgcolor=t["paper"],
            font=dict(family="DM Sans", size=11, color=t["text"]),
            showlegend=False,
        )
        st.plotly_chart(fig2, width="stretch")

    st.markdown(
        '<p class="section-label">Recency vs monetary · bubble = frequency</p>',
        unsafe_allow_html=True,
    )
    sample = rfm.sample(min(1500, len(rfm)), random_state=42)
    fig3 = px.scatter(
        sample, x="recency", y="monetary",
        size="frequency", color="segment",
        color_discrete_map=SEG_COLORS, size_max=20, opacity=0.65,
        labels={
            "recency":  "Days since last order (lower = better)",
            "monetary": "Total spend ($)",
        },
    )
    fig3.update_layout(
        height=320, margin=dict(l=0, r=0, t=5, b=0),
        plot_bgcolor=t["plot_bg"], paper_bgcolor=t["paper"],
        font=dict(family="DM Sans", size=12, color=t["text"]),
        xaxis=dict(showgrid=False, tickfont=dict(color=t["text"]),
                   title_font=dict(color=t["text"])),
        yaxis=dict(gridcolor=t["grid"], tickfont=dict(color=t["text"]),
                   title_font=dict(color=t["text"])),
        legend=dict(font=dict(size=10, color=t["text"])),
    )
    st.plotly_chart(fig3, width="stretch")

    st.markdown(
        '<p class="section-label">Segment playbook · recommended PM actions</p>',
        unsafe_allow_html=True,
    )
    selected_seg = st.selectbox("Select segment to see action", list(SEG_ACTIONS.keys()))
    seg_data = rfm[rfm["segment"] == selected_seg]

    p1, p2, p3 = st.columns(3)
    with p1: st.metric("Customers",      f"{len(seg_data):,}")
    with p2: st.metric("Avg LTV",        f"${seg_data['monetary'].mean():.0f}")
    with p3: st.metric("Avg Order Freq", f"{seg_data['frequency'].mean():.1f}x")

    box_type = "success" if selected_seg in ["Champions","Loyal","New Customers"] else "warning"
    st.markdown(
        f'<div class="insight-box {box_type}">🎯 <strong>{selected_seg}:</strong> {SEG_ACTIONS[selected_seg]}</div>',
        unsafe_allow_html=True,
    )
