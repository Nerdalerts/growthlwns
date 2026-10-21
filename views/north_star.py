import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from data.generator import get_daily_metrics, get_orders
import theme

def render():
    st.markdown('<p class="page-title">North Star Dashboard</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Top-line health metrics for your DTC business · 12-month rolling window</p>', unsafe_allow_html=True)

    daily = get_daily_metrics()
    orders = get_orders()

    # --- KPI row ---
    total_gmv    = orders["revenue"].sum()
    total_orders = len(orders)
    avg_aov      = orders["revenue"].mean()
    avg_daumau   = daily["dau_mau_ratio"].mean()

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total GMV", f"${total_gmv:,.0f}", delta="+18.4% YoY")
    with c2: st.metric("Total Orders", f"{total_orders:,}", delta="+12.1% YoY")
    with c3: st.metric("Avg Order Value", f"${avg_aov:.2f}", delta="+5.7% YoY")
    with c4: st.metric("Avg DAU/MAU", f"{avg_daumau:.1f}%", delta="+2.3pp YoY")

    st.markdown('<p class="section-label">GMV trend · monthly</p>', unsafe_allow_html=True)

    monthly_gmv = orders.groupby("month")["revenue"].sum().reset_index()
    monthly_gmv["month_str"] = monthly_gmv["month"].astype(str)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=monthly_gmv["month_str"],
        y=monthly_gmv["revenue"],
        marker_color="#3b82f6",
        marker_opacity=0.85,
        name="GMV",
    ))
    fig.add_trace(go.Scatter(
        x=monthly_gmv["month_str"],
        y=monthly_gmv["revenue"].rolling(3).mean(),
        mode="lines",
        line=dict(color=theme.font_color(), width=2, dash="dot"),
        name="3-mo avg",
    ))
    fig.update_layout(
        height=300, margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor=theme.plot_bg(), paper_bgcolor=theme.plot_bg(),
        font=dict(family="DM Sans", size=12, color="black"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(gridcolor=theme.grid_color(), tickprefix="$", tickformat=",.0f"),
    )
    st.plotly_chart(fig, width='stretch')

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<p class="section-label">Revenue by channel</p>', unsafe_allow_html=True)
        channel_rev = orders.groupby("channel")["revenue"].sum().sort_values(ascending=True).reset_index()
        fig2 = go.Figure(go.Bar(
            x=channel_rev["revenue"], y=channel_rev["channel"],
            orientation="h", marker_color="#3b82f6", marker_opacity=0.8,
        ))
        fig2.update_layout(
            height=250, margin=dict(l=0, r=0, t=5, b=0),
            plot_bgcolor=theme.plot_bg(), paper_bgcolor=theme.plot_bg(),
            font=dict(family="DM Sans", size=12, color="black"),
            xaxis=dict(gridcolor=theme.grid_color(), tickprefix="$", tickformat=",.0f"),
            yaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig2, width='stretch')

    with col_right:
        st.markdown('<p class="section-label">Revenue by category</p>', unsafe_allow_html=True)
        cat_rev = orders.groupby("category")["revenue"].sum().reset_index()
        fig3 = px.pie(
            cat_rev, names="category", values="revenue",
            color_discrete_sequence=["#3b82f6","#60a5fa","#93c5fd","#bfdbfe","#dbeafe"],
            hole=0.55,
        )
        fig3.update_traces(textposition="outside", textinfo="label+percent")
        fig3.update_layout(
            height=250, margin=dict(l=0, r=0, t=5, b=0),
            paper_bgcolor=theme.plot_bg(),
            font=dict(family="DM Sans", size=12, color="black"),
            showlegend=False,
        )
        st.plotly_chart(fig3, width='stretch')

    st.markdown('<p class="section-label">DAU / MAU stickiness · daily</p>', unsafe_allow_html=True)
    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(
        x=daily["date"], y=daily["dau_mau_ratio"],
        fill="tozeroy", fillcolor="rgba(59,130,246,0.08)",
        line=dict(color="#3b82f6", width=1.5),
        name="DAU/MAU %",
    ))
    fig4.update_layout(
        height=200, margin=dict(l=0, r=0, t=5, b=0),
        plot_bgcolor=theme.plot_bg(), paper_bgcolor=theme.plot_bg(),
        font=dict(family="DM Sans", size=12, color="black"),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor=theme.grid_color(), ticksuffix="%"),
    )
    st.plotly_chart(fig4, width='stretch')

    st.markdown('<div class="insight-box">📌 <strong>PM Insight:</strong> DAU/MAU ratio averages ~34% — healthy for DTC. Watch for dips below 28% as an early churn signal. Paid Social drives the most GMV but Email has the highest AOV ($71 avg) — strong candidate for upsell/cross-sell investment.</div>', unsafe_allow_html=True)
