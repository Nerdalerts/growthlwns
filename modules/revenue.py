import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from data.loader import get_orders


def _t():
    return {
        "plot_bg": st.session_state.get("_plot_bg", "#ffffff"),
        "paper":   st.session_state.get("_plot_paper", "#ffffff"),
        "grid":    st.session_state.get("_grid", "#f0f0f0"),
        "bar":     st.session_state.get("_bar_color", "#3b82f6"),
        "text":    st.session_state.get("_text", "#111"),
    }


def render():
    st.markdown('<p class="page-title">Revenue Analytics</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-subtitle">MoM growth, AOV trends, category & channel breakdown · follow the money</p>',
        unsafe_allow_html=True,
    )

    orders = get_orders()
    t      = _t()

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        cat_filter = st.multiselect(
            "Category",
            options=sorted(orders["category"].unique()),
            default=list(orders["category"].unique()),
        )
    with col_f2:
        ch_filter = st.multiselect(
            "Channel",
            options=sorted(orders["channel"].unique()),
            default=list(orders["channel"].unique()),
        )

    filtered = orders[
        orders["category"].isin(cat_filter) & orders["channel"].isin(ch_filter)
    ]

    if filtered.empty:
        st.warning("No data for the selected filters.")
        return

    monthly = (
        filtered.groupby("month")
        .agg(revenue=("revenue","sum"), orders=("order_id","count"),
             aov=("revenue","mean"), unique_buyers=("user_id","nunique"))
        .reset_index()
    )
    monthly["month_str"]  = monthly["month"].astype(str)
    monthly["mom_growth"] = monthly["revenue"].pct_change() * 100

    total_rev  = filtered["revenue"].sum()
    avg_aov    = filtered["revenue"].mean()
    best_month = monthly.loc[monthly["revenue"].idxmax(), "month_str"]
    peak_rev   = monthly["revenue"].max()

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total Revenue", f"${total_rev:,.0f}")
    with c2: st.metric("Avg AOV",       f"${avg_aov:.2f}")
    with c3: st.metric("Peak Month",    best_month)
    with c4: st.metric("Peak Revenue",  f"${peak_rev:,.0f}")

    # ── Monthly revenue vs AOV ─────────────────────────────────────────────
    st.markdown('<p class="section-label">Monthly revenue vs AOV</p>', unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=monthly["month_str"], y=monthly["revenue"],
        name="Revenue", marker_color=t["bar"], marker_opacity=0.8, yaxis="y",
    ))
    fig.add_trace(go.Scatter(
        x=monthly["month_str"], y=monthly["aov"],
        name="AOV", mode="lines+markers",
        line=dict(color="#f59e0b", width=2), marker=dict(size=6), yaxis="y2",
    ))
    fig.update_layout(
        height=300, margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor=t["plot_bg"], paper_bgcolor=t["paper"],
        font=dict(family="DM Sans", size=12, color=t["text"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    font=dict(color=t["text"])),
        xaxis=dict(showgrid=False, tickfont=dict(color=t["text"])),
        yaxis=dict(title="Revenue ($)", gridcolor=t["grid"],
                   tickprefix="$", tickformat=",.0f",
                   tickfont=dict(color=t["text"]), title_font=dict(color=t["text"])),
        yaxis2=dict(title="AOV ($)", overlaying="y", side="right", showgrid=False,
                    tickprefix="$", tickfont=dict(color=t["text"]),
                    title_font=dict(color=t["text"])),
    )
    st.plotly_chart(fig, width="stretch")

    # ── MoM growth ────────────────────────────────────────────────────────
    st.markdown('<p class="section-label">Month-over-month growth (%)</p>', unsafe_allow_html=True)
    mom = monthly.dropna(subset=["mom_growth"])
    fig2 = go.Figure(go.Bar(
        x=mom["month_str"], y=mom["mom_growth"].round(1),
        marker_color=["#22c55e" if v >= 0 else "#ef4444" for v in mom["mom_growth"]],
        text=[f"{v:.1f}%" for v in mom["mom_growth"]],
        textposition="outside",
        textfont=dict(color=t["text"]),
    ))
    fig2.add_hline(y=0, line_color=t["text"], line_width=0.5)
    fig2.update_layout(
        height=220, margin=dict(l=0, r=0, t=20, b=0),
        plot_bgcolor=t["plot_bg"], paper_bgcolor=t["paper"],
        font=dict(family="DM Sans", size=12, color=t["text"]),
        xaxis=dict(showgrid=False, tickfont=dict(color=t["text"])),
        yaxis=dict(gridcolor=t["grid"], ticksuffix="%",
                   tickfont=dict(color=t["text"])),
    )
    st.plotly_chart(fig2, width="stretch")

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown('<p class="section-label">Revenue by category · monthly</p>', unsafe_allow_html=True)
        cat_month = filtered.groupby(["month","category"])["revenue"].sum().reset_index()
        cat_month["month_str"] = cat_month["month"].astype(str)
        fig3 = px.area(
            cat_month, x="month_str", y="revenue", color="category",
            color_discrete_sequence=["#1d4ed8","#3b82f6","#60a5fa","#93c5fd","#bfdbfe",
                                     "#2563eb","#7c3aed","#a78bfa","#22c55e","#f59e0b"],
        )
        fig3.update_layout(
            height=260, margin=dict(l=0, r=0, t=5, b=0),
            plot_bgcolor=t["plot_bg"], paper_bgcolor=t["paper"],
            font=dict(family="DM Sans", size=11, color=t["text"]),
            legend=dict(font=dict(size=10, color=t["text"])),
            xaxis=dict(showgrid=False, title="",
                       tickfont=dict(color=t["text"])),
            yaxis=dict(gridcolor=t["grid"], tickprefix="$", tickformat=",.0f",
                       title="", tickfont=dict(color=t["text"])),
        )
        st.plotly_chart(fig3, width="stretch")

    with col_r:
        st.markdown('<p class="section-label">AOV by channel</p>', unsafe_allow_html=True)
        ch_aov = filtered.groupby("channel")["revenue"].mean().sort_values(ascending=True).reset_index()
        fig4 = go.Figure(go.Bar(
            x=ch_aov["revenue"].round(2), y=ch_aov["channel"],
            orientation="h", marker_color=t["bar"],
            text=[f"${v:.0f}" for v in ch_aov["revenue"]],
            textposition="outside",
            textfont=dict(color=t["text"]),
        ))
        fig4.update_layout(
            height=260, margin=dict(l=0, r=40, t=5, b=0),
            plot_bgcolor=t["plot_bg"], paper_bgcolor=t["paper"],
            font=dict(family="DM Sans", size=12, color=t["text"]),
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(showgrid=False, tickfont=dict(color=t["text"])),
        )
        st.plotly_chart(fig4, width="stretch")

    st.markdown(
        '<div class="insight-box success">📌 <strong>PM Insight:</strong> '
        "Health Beauty and Watches Gifts tend to have the highest AOV. "
        "Boleto payment correlates with lower repeat purchase — these buyers respond well to instalment promotions. "
        "Q4 months consistently outperform — plan inventory and paid media accordingly.</div>",
        unsafe_allow_html=True,
    )
