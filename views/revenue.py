import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from data.generator import get_orders
import theme

def render():
    st.markdown('<p class="page-title">Revenue Analytics</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">MoM growth, AOV trends, category & channel breakdown · follow the money</p>', unsafe_allow_html=True)

    orders = get_orders()

    # --- Filters ---
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        cat_filter = st.multiselect(
            "Category",
            options=sorted(orders["category"].unique()),
            default=sorted(orders["category"].unique()),
            key="revenue_cat_filter",
        )
    with col_f2:
        ch_filter = st.multiselect(
            "Channel",
            options=sorted(orders["channel"].unique()),
            default=sorted(orders["channel"].unique()),
            key="revenue_ch_filter",
        )

    filtered = orders[orders["category"].isin(cat_filter) & orders["channel"].isin(ch_filter)]

    if filtered.empty:
        st.warning("No data found for the selected category/channel filters. Please select at least one category and channel above.")
        return

    # --- Monthly aggregation ---
    monthly = filtered.groupby("month").agg(
        revenue=("revenue","sum"),
        orders=("order_id","count"),
        aov=("revenue","mean"),
        unique_buyers=("user_id","nunique"),
    ).reset_index()
    monthly["month_str"] = monthly["month"].astype(str)
    monthly["mom_growth"] = monthly["revenue"].pct_change() * 100

    if monthly.empty:
        st.warning("No monthly aggregate data found for current filters.")
        return

    # --- KPIs ---
    total_rev  = filtered["revenue"].sum()
    avg_aov    = filtered["revenue"].mean()
    best_month = monthly.loc[monthly["revenue"].idxmax(), "month_str"] if monthly["revenue"].notna().any() else "N/A"
    peak_rev   = monthly["revenue"].max() if monthly["revenue"].notna().any() else 0.0

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total Revenue", f"${total_rev:,.0f}")
    with c2: st.metric("Avg AOV", f"${avg_aov:.2f}")
    with c3: st.metric("Peak Month", best_month)
    with c4: st.metric("Peak Revenue", f"${peak_rev:,.0f}")

    # --- Revenue + AOV dual axis ---
    st.markdown('<p class="section-label">Monthly revenue vs AOV</p>', unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=monthly["month_str"], y=monthly["revenue"],
        name="Revenue", marker_color="#3b82f6", marker_opacity=0.8, yaxis="y",
    ))
    fig.add_trace(go.Scatter(
        x=monthly["month_str"], y=monthly["aov"],
        name="AOV", mode="lines+markers",
        line=dict(color="#f59e0b", width=2), marker=dict(size=6),
        yaxis="y2",
    ))
    fig.update_layout(
        height=300, margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor=theme.plot_bg(), paper_bgcolor=theme.plot_bg(),
        font=dict(family="DM Sans", size=12, color="black"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis=dict(showgrid=False),
        yaxis=dict(title="Revenue ($)", gridcolor=theme.grid_color(), tickprefix="$", tickformat=",.0f"),
        yaxis2=dict(title="AOV ($)", overlaying="y", side="right", showgrid=False, tickprefix="$"),
    )
    st.plotly_chart(fig, width='stretch')

    # --- MoM growth ---
    st.markdown('<p class="section-label">Month-over-month growth (%)</p>', unsafe_allow_html=True)
    fig2 = go.Figure(go.Bar(
        x=monthly["month_str"][1:], y=monthly["mom_growth"][1:].round(1),
        marker_color=["#22c55e" if v >= 0 else "#ef4444" for v in monthly["mom_growth"][1:]],
        text=[f"{v:.1f}%" for v in monthly["mom_growth"][1:]],
        textposition="outside",
    ))
    fig2.add_hline(y=0, line_color=theme.font_color(), line_width=0.5)
    fig2.update_layout(
        height=220, margin=dict(l=0, r=0, t=20, b=0),
        plot_bgcolor=theme.plot_bg(), paper_bgcolor=theme.plot_bg(),
        font=dict(family="DM Sans", size=12, color="black"),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor=theme.grid_color(), ticksuffix="%"),
    )
    st.plotly_chart(fig2, width='stretch')

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown('<p class="section-label">Revenue by category · monthly</p>', unsafe_allow_html=True)
        cat_month = filtered.groupby(["month","category"])["revenue"].sum().reset_index()
        cat_month["month_str"] = cat_month["month"].astype(str)
        fig3 = px.area(
            cat_month, x="month_str", y="revenue", color="category",
            color_discrete_sequence=["#1d4ed8","#3b82f6","#60a5fa","#93c5fd","#bfdbfe"],
        )
        fig3.update_layout(
            height=260, margin=dict(l=0, r=0, t=5, b=0),
            plot_bgcolor=theme.plot_bg(), paper_bgcolor=theme.plot_bg(),
            font=dict(family="DM Sans", size=11, color="black"),
            legend=dict(font=dict(size=10)),
            xaxis=dict(showgrid=False, title=""),
            yaxis=dict(gridcolor=theme.grid_color(), tickprefix="$", tickformat=",.0f", title=""),
        )
        st.plotly_chart(fig3, width='stretch')

    with col_r:
        st.markdown('<p class="section-label">AOV by channel</p>', unsafe_allow_html=True)
        ch_aov = filtered.groupby("channel")["revenue"].mean().sort_values(ascending=True).reset_index()
        fig4 = go.Figure(go.Bar(
            x=ch_aov["revenue"].round(2), y=ch_aov["channel"],
            orientation="h", marker_color="#3b82f6",
            text=[f"${v:.0f}" for v in ch_aov["revenue"]],
            textposition="outside",
        ))
        fig4.update_layout(
            height=260, margin=dict(l=0, r=40, t=5, b=0),
            plot_bgcolor=theme.plot_bg(), paper_bgcolor=theme.plot_bg(),
            font=dict(family="DM Sans", size=12, color="black"),
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig4, width='stretch')

    st.markdown('<div class="insight-box success">📌 <strong>PM Insight:</strong> Apparel has the highest AOV ($85) but the lowest order frequency. A bundle promotion with Accessories could lift basket size. Email channel drives the second-highest AOV — consider increasing email frequency for high-LTV segments identified in RFM.</div>', unsafe_allow_html=True)