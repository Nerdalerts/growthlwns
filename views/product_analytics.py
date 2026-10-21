import streamlit as st
import plotly.graph_objects as go
from data.generator import get_product_analytics, get_orders
import theme

def render():
    st.markdown('<p class="page-title">Product Analytics</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Page performance, bounce rate, scroll depth & device split · where users engage and bail</p>', unsafe_allow_html=True)

    pa     = get_product_analytics()
    orders = get_orders()

    top_page     = pa.loc[pa["sessions"].idxmax(),"page"]
    worst_bounce = pa.loc[pa["bounce_rate"].idxmax(),"page"]
    best_scroll  = pa.loc[pa["scroll_depth"].idxmax(),"page"]
    pdp_atc      = pa.loc[pa["page"]=="PDP","add_to_cart_rate"].values[0]

    c1,c2,c3,c4 = st.columns(4)
    with c1: st.metric("Most Visited",       top_page)
    with c2: st.metric("Highest Bounce",     worst_bounce)
    with c3: st.metric("Best Scroll Depth",  best_scroll)
    with c4: st.metric("PDP Add-to-Cart",    f"{pdp_atc*100:.1f}%")

    st.markdown('<p class="section-label">Sessions by page</p>', unsafe_allow_html=True)
    pa_s = pa.sort_values("sessions", ascending=True)
    fig = go.Figure(go.Bar(
        x=pa_s["sessions"], y=pa_s["page"], orientation="h",
        marker_color="#3b82f6", marker_opacity=0.85,
        text=[f"{s:,}" for s in pa_s["sessions"]], textposition="outside",
    ))
    fig.update_layout(
        height=280, margin=dict(l=0,r=60,t=5,b=0),
        plot_bgcolor=theme.plot_bg(), paper_bgcolor=theme.plot_bg(),
        font=dict(family="DM Sans", size=12, color="black"),
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=False),
    )
    st.plotly_chart(fig, width='stretch')

    cl, cr = st.columns(2)
    with cl:
        st.markdown('<p class="section-label">Bounce rate by page</p>', unsafe_allow_html=True)
        pa_b = pa.sort_values("bounce_rate", ascending=True)
        fig2 = go.Figure(go.Bar(
            x=pa_b["bounce_rate"]*100, y=pa_b["page"], orientation="h",
            marker_color=["#ef4444" if v>0.55 else "#f59e0b" if v>0.40 else "#22c55e" for v in pa_b["bounce_rate"]],
            text=[f"{v*100:.0f}%" for v in pa_b["bounce_rate"]], textposition="outside",
        ))
        fig2.update_layout(
            height=280, margin=dict(l=0,r=60,t=5,b=0),
            plot_bgcolor=theme.plot_bg(), paper_bgcolor=theme.plot_bg(),
            font=dict(family="DM Sans", size=12, color="black"),
            xaxis=dict(showgrid=False, ticksuffix="%", range=[0,90]),
            yaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig2, width='stretch')

    with cr:
        st.markdown('<p class="section-label">Scroll depth by page</p>', unsafe_allow_html=True)
        pa_sc = pa.sort_values("scroll_depth", ascending=True)
        fig3 = go.Figure(go.Bar(
            x=pa_sc["scroll_depth"]*100, y=pa_sc["page"], orientation="h",
            marker_color=["#22c55e" if v>0.65 else "#f59e0b" if v>0.50 else "#ef4444" for v in pa_sc["scroll_depth"]],
            text=[f"{v*100:.0f}%" for v in pa_sc["scroll_depth"]], textposition="outside",
        ))
        fig3.update_layout(
            height=280, margin=dict(l=0,r=60,t=5,b=0),
            plot_bgcolor=theme.plot_bg(), paper_bgcolor=theme.plot_bg(),
            font=dict(family="DM Sans", size=12, color="black"),
            xaxis=dict(showgrid=False, ticksuffix="%", range=[0,110]),
            yaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig3, width='stretch')

    st.markdown('<p class="section-label">Avg time on page (seconds)</p>', unsafe_allow_html=True)
    pa_t = pa.sort_values("avg_time_sec", ascending=False)
    fig4 = go.Figure(go.Bar(
        x=pa_t["page"], y=pa_t["avg_time_sec"], marker_color="#60a5fa",
        text=[f"{v}s" for v in pa_t["avg_time_sec"]], textposition="outside",
    ))
    fig4.update_layout(
        height=220, margin=dict(l=0,r=0,t=20,b=0),
        plot_bgcolor=theme.plot_bg(), paper_bgcolor=theme.plot_bg(),
        font=dict(family="DM Sans", size=12, color="black"),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor=theme.grid_color(), title="Seconds"),
    )
    st.plotly_chart(fig4, width='stretch')

    device_orders = orders.groupby("device")["order_id"].count().reset_index()
    device_orders.columns = ["device","orders"]
    st.markdown('<p class="section-label">Orders by device</p>', unsafe_allow_html=True)
    col_dev, _ = st.columns([1,2])
    with col_dev:
        fig5 = go.Figure(go.Pie(
            labels=device_orders["device"], values=device_orders["orders"],
            hole=0.5, marker_colors=["#3b82f6","#60a5fa","#bfdbfe"],
            textinfo="label+percent",
        ))
        fig5.update_layout(
            height=220, margin=dict(l=0,r=0,t=5,b=0),
            paper_bgcolor=theme.plot_bg(),
            font=dict(family="DM Sans", size=12, color="black"),
            showlegend=False,
        )
        st.plotly_chart(fig5, width='stretch')

    st.markdown('<div class="insight-box warning">⚠️ <strong>PM Insight:</strong> Blog and Search Results have the highest bounce rates. PDP scroll depth past 70% is a strong purchase-intent signal. 62% of orders come from mobile but mobile CVR lags desktop — prioritise mobile PDP optimisation.</div>', unsafe_allow_html=True)
