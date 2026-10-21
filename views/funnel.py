import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from data.generator import get_funnel, get_orders
import theme

def render():
    st.markdown('<p class="page-title">Funnel Analysis</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Conversion drop-off from visit to purchase · identify where you\'re losing buyers</p>', unsafe_allow_html=True)

    df = get_funnel()
    orders = get_orders()

    # --- Filters ---
    col_f1, col_f2 = st.columns([2, 3])
    with col_f1:
        device_filter = st.selectbox("Device", ["All", "Mobile", "Desktop", "Tablet"])

    # Device multipliers to simulate filtered funnels
    device_mult = {"All": 1.0, "Mobile": 0.62, "Desktop": 0.31, "Tablet": 0.07}
    conv_adj    = {"All": 1.0, "Mobile": 0.88, "Desktop": 1.12, "Tablet": 0.95}
    mult = device_mult[device_filter]
    adj  = conv_adj[device_filter]

    df_filtered = df.copy()
    df_filtered["users"] = (df_filtered["users"] * mult * (1 + (adj - 1) * df_filtered["stage_order"] / 5)).astype(int)

    # --- Conversion rates ---
    df_filtered["cvr_from_prev"] = df_filtered["users"] / df_filtered["users"].shift(1)
    df_filtered["cvr_from_top"]  = df_filtered["users"] / df_filtered["users"].iloc[0]
    df_filtered["drop_abs"]      = df_filtered["users"].shift(1) - df_filtered["users"]

    # --- KPIs ---
    overall_cvr = df_filtered["users"].iloc[-1] / df_filtered["users"].iloc[0] * 100
    top_drop_idx = df_filtered["drop_abs"].idxmax()
    top_drop_stage = df_filtered.loc[top_drop_idx, "stage"]

    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Overall CVR", f"{overall_cvr:.2f}%")
    with c2: st.metric("Biggest Drop-off", top_drop_stage)
    with c3: st.metric("Purchase Volume", f"{df_filtered['users'].iloc[-1]:,}")

    st.markdown('<p class="section-label">Conversion funnel</p>', unsafe_allow_html=True)

    # Funnel chart
    fig = go.Figure(go.Funnel(
        y=df_filtered["stage"],
        x=df_filtered["users"],
        textposition="inside",
        textinfo="value+percent previous",
        opacity=0.88,
        marker=dict(
            color=["#1d4ed8","#2563eb","#3b82f6","#60a5fa","#93c5fd"],
            line=dict(width=1, color="#fff"),
        ),
        connector=dict(line=dict(color="#e0e7ff", width=2)),
    ))
    fig.update_layout(
        height=380, margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor=theme.plot_bg(), plot_bgcolor=theme.plot_bg(),
        font=dict(family="DM Sans", size=13, color="black"),
    )
    st.plotly_chart(fig, width='stretch')

    # Step-by-step table
    st.markdown('<p class="section-label">Step-by-step breakdown</p>', unsafe_allow_html=True)

    display = df_filtered[["stage","users","cvr_from_prev","drop_abs"]].copy()
    display.columns = ["Stage", "Users", "CVR from prev step", "Users lost"]
    display["CVR from prev step"] = display["CVR from prev step"].apply(
        lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—"
    )
    display["Users lost"] = display["Users lost"].apply(
        lambda x: f"{int(x):,}" if pd.notna(x) else "—"
    )
    display["Users"] = display["Users"].apply(lambda x: f"{x:,}")
    st.dataframe(display, width='stretch', hide_index=True)

    # Funnel by channel
    st.markdown('<p class="section-label">Purchase CVR by channel</p>', unsafe_allow_html=True)

    channel_cvr = orders.groupby("channel").agg(
        orders=("order_id","count")
    ).reset_index()
    channel_cvr["cvr"] = (channel_cvr["orders"] / channel_cvr["orders"].sum() * overall_cvr * 6).round(2)
    channel_cvr = channel_cvr.sort_values("cvr", ascending=True)

    fig2 = go.Figure(go.Bar(
        x=channel_cvr["cvr"], y=channel_cvr["channel"],
        orientation="h",
        marker_color=["#bfdbfe" if v < channel_cvr["cvr"].median() else "#3b82f6" for v in channel_cvr["cvr"]],
        text=[f"{v:.1f}%" for v in channel_cvr["cvr"]],
        textposition="outside",
    ))
    fig2.update_layout(
        height=250, margin=dict(l=0, r=40, t=5, b=0),
        plot_bgcolor=theme.plot_bg(), paper_bgcolor=theme.plot_bg(),
        font=dict(family="DM Sans", size=12, color="black"),
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=False),
    )
    st.plotly_chart(fig2, width='stretch')

    st.markdown('<div class="insight-box warning">⚠️ <strong>PM Insight:</strong> The Visit → PDP drop (~45%) is the largest opportunity. A/B test improved category page merchandising and search relevance to lift PDP view rate. Cart → Checkout is also below benchmark — investigate friction in the cart experience (guest checkout, trust signals, shipping cost reveal).</div>', unsafe_allow_html=True)