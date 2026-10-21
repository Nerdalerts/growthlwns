import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from data.loader import get_product_analytics


def _t():
    return {
        "plot_bg": st.session_state.get("_plot_bg", "#ffffff"),
        "paper":   st.session_state.get("_plot_paper", "#ffffff"),
        "grid":    st.session_state.get("_grid", "#f0f0f0"),
        "bar":     st.session_state.get("_bar_color", "#3b82f6"),
        "text":    st.session_state.get("_text", "#111"),
    }


def render():
    st.markdown('<p class="page-title">Product Analytics</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-subtitle">Category-level performance · sessions, engagement, and revenue by product segment</p>',
        unsafe_allow_html=True,
    )

    pa = get_product_analytics()
    t  = _t()

    total_sessions = pa["sessions"].sum()
    avg_bounce     = pa["bounce_rate"].mean()
    avg_scroll     = pa["scroll_depth"].mean()
    top_category   = pa.loc[pa["revenue"].idxmax(), "page"]

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total Est. Sessions",  f"{total_sessions:,}")
    with c2: st.metric("Avg Bounce Rate",      f"{avg_bounce*100:.1f}%")
    with c3: st.metric("Avg Scroll Depth",     f"{avg_scroll*100:.0f}%")
    with c4: st.metric("Top Revenue Category", top_category)

    # ── Sessions bar ──────────────────────────────────────────────────────
    st.markdown('<p class="section-label">Sessions by category</p>', unsafe_allow_html=True)
    fig = go.Figure(go.Bar(
        x=pa["sessions"], y=pa["page"], orientation="h",
        marker_color=t["bar"], marker_opacity=0.85,
        text=[f"{v:,}" for v in pa["sessions"]],
        textposition="outside",
        textfont=dict(color=t["text"]),
    ))
    fig.update_layout(
        height=max(300, len(pa) * 32), margin=dict(l=0, r=80, t=5, b=0),
        plot_bgcolor=t["plot_bg"], paper_bgcolor=t["paper"],
        font=dict(family="DM Sans", size=12, color=t["text"]),
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=False, categoryorder="total ascending",
                   tickfont=dict(color=t["text"])),
    )
    st.plotly_chart(fig, width="stretch")

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown('<p class="section-label">Bounce rate vs scroll depth</p>', unsafe_allow_html=True)
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=pa["page"], y=pa["bounce_rate"] * 100,
            name="Bounce %", marker_color="#ef4444", marker_opacity=0.7,
        ))
        fig2.add_trace(go.Scatter(
            x=pa["page"], y=pa["scroll_depth"] * 100,
            name="Scroll depth %", mode="lines+markers",
            line=dict(color="#22c55e", width=2), marker=dict(size=7), yaxis="y2",
        ))
        fig2.update_layout(
            height=280, margin=dict(l=0, r=0, t=5, b=0),
            plot_bgcolor=t["plot_bg"], paper_bgcolor=t["paper"],
            font=dict(family="DM Sans", size=11, color=t["text"]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                        font=dict(color=t["text"])),
            xaxis=dict(showgrid=False, tickangle=-30,
                       tickfont=dict(color=t["text"])),
            yaxis=dict(title="Bounce %", gridcolor=t["grid"], ticksuffix="%",
                       tickfont=dict(color=t["text"]), title_font=dict(color=t["text"])),
            yaxis2=dict(title="Scroll %", overlaying="y", side="right",
                        showgrid=False, ticksuffix="%",
                        tickfont=dict(color=t["text"]), title_font=dict(color=t["text"])),
        )
        st.plotly_chart(fig2, width="stretch")

    with col_r:
        st.markdown('<p class="section-label">Revenue share by category</p>', unsafe_allow_html=True)
        fig3 = px.pie(
            pa, names="page", values="revenue",
            color_discrete_sequence=["#3b82f6","#60a5fa","#1d4ed8","#93c5fd","#bfdbfe",
                                     "#2563eb","#7c3aed","#a78bfa","#22c55e","#f59e0b"],
            hole=0.5,
        )
        fig3.update_traces(textposition="outside", textinfo="label+percent",
                           textfont_color=t["text"])
        fig3.update_layout(
            height=280, margin=dict(l=0, r=0, t=5, b=0),
            paper_bgcolor=t["paper"],
            font=dict(family="DM Sans", size=10, color=t["text"]),
            showlegend=False,
        )
        st.plotly_chart(fig3, width="stretch")

    # ── Avg time ─────────────────────────────────────────────────────────
    st.markdown('<p class="section-label">Avg time on page · seconds</p>', unsafe_allow_html=True)
    pa_s = pa.sort_values("avg_time_sec", ascending=True)
    median_time = pa_s["avg_time_sec"].median()
    fig4 = go.Figure(go.Bar(
        x=pa_s["avg_time_sec"], y=pa_s["page"], orientation="h",
        marker_color=[t["bar"] if v > median_time else "#bfdbfe" for v in pa_s["avg_time_sec"]],
        text=[f"{v}s" for v in pa_s["avg_time_sec"]],
        textposition="outside",
        textfont=dict(color=t["text"]),
    ))
    fig4.update_layout(
        height=max(280, len(pa) * 32), margin=dict(l=0, r=60, t=5, b=0),
        plot_bgcolor=t["plot_bg"], paper_bgcolor=t["paper"],
        font=dict(family="DM Sans", size=12, color=t["text"]),
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=False, tickfont=dict(color=t["text"])),
    )
    st.plotly_chart(fig4, width="stretch")

    # ── Full table ───────────────────────────────────────────────────────
    st.markdown('<p class="section-label">Full category breakdown</p>', unsafe_allow_html=True)
    display = pa[["page","sessions","bounce_rate","scroll_depth","avg_time_sec","revenue"]].copy()
    display.columns = ["Category","Sessions","Bounce Rate","Scroll Depth","Avg Time (s)","Revenue ($)"]
    display["Bounce Rate"]  = display["Bounce Rate"].apply(lambda x: f"{x*100:.0f}%")
    display["Scroll Depth"] = display["Scroll Depth"].apply(lambda x: f"{x*100:.0f}%")
    display["Sessions"]     = display["Sessions"].apply(lambda x: f"{x:,}")
    display["Revenue ($)"]  = display["Revenue ($)"].apply(lambda x: f"${x:,.0f}")
    st.dataframe(display, width="stretch", hide_index=True)

    st.markdown(
        '<div class="insight-box">📌 <strong>PM Insight:</strong> '
        "High bounce + low scroll depth categories are prime candidates for content and UX improvements. "
        "High session count but low revenue may signal pricing or trust issues. "
        "Focus A/B testing budget on the top 3 categories by session volume first.</div>",
        unsafe_allow_html=True,
    )
