import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from data.loader import get_daily_metrics, get_orders


def _t():
    return {
        "plot_bg":   st.session_state.get("_plot_bg", "#ffffff"),
        "paper":     st.session_state.get("_plot_paper", "#ffffff"),
        "grid":      st.session_state.get("_grid", "#f0f0f0"),
        "bar":       st.session_state.get("_bar_color", "#3b82f6"),
        "text":      st.session_state.get("_text", "#111"),
    }


def render():
    st.markdown('<p class="page-title">North Star Dashboard</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-subtitle">Top-line health metrics · rolling window</p>',
        unsafe_allow_html=True,
    )

    daily  = get_daily_metrics()
    orders = get_orders()
    t      = _t()

    total_gmv    = orders["revenue"].sum()
    total_orders = len(orders)
    avg_aov      = orders["revenue"].mean()
    avg_daumau   = daily["dau_mau_ratio"].mean()

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total GMV",       f"${total_gmv:,.0f}")
    with c2: st.metric("Total Orders",    f"{total_orders:,}")
    with c3: st.metric("Avg Order Value", f"${avg_aov:.2f}")
    with c4: st.metric("Avg DAU/MAU",     f"{avg_daumau:.1f}%")

    st.markdown('<p class="section-label">GMV trend · monthly</p>', unsafe_allow_html=True)
    monthly_gmv = orders.groupby("month")["revenue"].sum().reset_index()
    monthly_gmv["month_str"] = monthly_gmv["month"].astype(str)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=monthly_gmv["month_str"], y=monthly_gmv["revenue"],
        marker_color=t["bar"], marker_opacity=0.85, name="GMV",
    ))
    fig.add_trace(go.Scatter(
        x=monthly_gmv["month_str"],
        y=monthly_gmv["revenue"].rolling(3).mean(),
        mode="lines", line=dict(color=t["text"], width=2, dash="dot"),
        name="3-mo avg",
    ))
    fig.update_layout(
        height=300, margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor=t["plot_bg"], paper_bgcolor=t["paper"],
        font=dict(family="DM Sans", size=12, color=t["text"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=False, tickfont=dict(size=11, color=t["text"])),
        yaxis=dict(gridcolor=t["grid"], tickprefix="$", tickformat=",.0f",
                   tickfont=dict(color=t["text"])),
    )
    st.plotly_chart(fig, width="stretch")

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<p class="section-label">Revenue by channel</p>', unsafe_allow_html=True)
        channel_rev = orders.groupby("channel")["revenue"].sum().sort_values(ascending=True).reset_index()
        fig2 = go.Figure(go.Bar(
            x=channel_rev["revenue"], y=channel_rev["channel"],
            orientation="h", marker_color=t["bar"], marker_opacity=0.8,
        ))
        fig2.update_layout(
            height=250, margin=dict(l=0, r=0, t=5, b=0),
            plot_bgcolor=t["plot_bg"], paper_bgcolor=t["paper"],
            font=dict(family="DM Sans", size=12, color=t["text"]),
            xaxis=dict(gridcolor=t["grid"], tickprefix="$", tickformat=",.0f",
                       tickfont=dict(color=t["text"])),
            yaxis=dict(showgrid=False, tickfont=dict(color=t["text"])),
        )
        st.plotly_chart(fig2, width="stretch")

    with col_right:
        st.markdown('<p class="section-label">Revenue by category</p>', unsafe_allow_html=True)
        cat_rev = orders.groupby("category")["revenue"].sum().reset_index()
        fig3 = px.pie(
            cat_rev, names="category", values="revenue",
            color_discrete_sequence=["#3b82f6","#60a5fa","#93c5fd","#bfdbfe","#dbeafe",
                                     "#1d4ed8","#2563eb","#7c3aed","#a78bfa","#c4b5fd"],
            hole=0.55,
        )
        fig3.update_traces(textposition="outside", textinfo="label+percent",
                           textfont_color=t["text"])
        fig3.update_layout(
            height=250, margin=dict(l=0, r=0, t=5, b=0),
            paper_bgcolor=t["paper"],
            font=dict(family="DM Sans", size=11, color=t["text"]),
            showlegend=False,
        )
        st.plotly_chart(fig3, width="stretch")

    st.markdown('<p class="section-label">DAU / MAU stickiness · daily</p>', unsafe_allow_html=True)
    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(
        x=daily["date"], y=daily["dau_mau_ratio"],
        fill="tozeroy", fillcolor="rgba(59,130,246,0.08)",
        line=dict(color=t["bar"], width=1.5), name="DAU/MAU %",
    ))
    fig4.update_layout(
        height=200, margin=dict(l=0, r=0, t=5, b=0),
        plot_bgcolor=t["plot_bg"], paper_bgcolor=t["paper"],
        font=dict(family="DM Sans", size=12, color=t["text"]),
        xaxis=dict(showgrid=False, tickfont=dict(color=t["text"])),
        yaxis=dict(gridcolor=t["grid"], ticksuffix="%", tickfont=dict(color=t["text"])),
    )
    st.plotly_chart(fig4, width="stretch")

    st.markdown(
        '<div class="insight-box">📌 <strong>PM Insight:</strong> '
        "DAU/MAU ~14% is typical for marketplace e-commerce. "
        "Credit Card drives the most GMV; Voucher buyers show the highest repeat rate — "
        "strong signal for a loyalty programme. "
        "Watch for monthly GMV dips as early churn signals.</div>",
        unsafe_allow_html=True,
    )
