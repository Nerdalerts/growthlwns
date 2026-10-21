import streamlit as st
import numpy as np
from scipy import stats
import plotly.graph_objects as go
import math


def _t():
    return {
        "plot_bg": st.session_state.get("_plot_bg", "#ffffff"),
        "paper":   st.session_state.get("_plot_paper", "#ffffff"),
        "grid":    st.session_state.get("_grid", "#f0f0f0"),
        "bar":     st.session_state.get("_bar_color", "#3b82f6"),
        "text":    st.session_state.get("_text", "#111"),
    }


def required_sample_size(baseline_cr, mde, alpha=0.05, power=0.80):
    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_beta  = stats.norm.ppf(power)
    p1 = baseline_cr
    p2 = baseline_cr * (1 + mde)
    p_pool = (p1 + p2) / 2
    n = (z_alpha * math.sqrt(2 * p_pool * (1 - p_pool)) +
         z_beta  * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2 / (p2 - p1) ** 2
    return math.ceil(n)


def run_ztest(n_control, conv_control, n_variant, conv_variant):
    p_c    = conv_control / n_control
    p_v    = conv_variant / n_variant
    p_pool = (conv_control + conv_variant) / (n_control + n_variant)
    se     = math.sqrt(p_pool * (1 - p_pool) * (1 / n_control + 1 / n_variant))
    z      = (p_v - p_c) / se if se > 0 else 0
    p_val  = 2 * (1 - stats.norm.cdf(abs(z)))
    ci_low  = (p_v - p_c) - 1.96 * math.sqrt(p_c*(1-p_c)/n_control + p_v*(1-p_v)/n_variant)
    ci_high = (p_v - p_c) + 1.96 * math.sqrt(p_c*(1-p_c)/n_control + p_v*(1-p_v)/n_variant)
    return p_c, p_v, z, p_val, ci_low, ci_high


def render():
    st.markdown('<p class="page-title">A/B Test Engine</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-subtitle">Design experiments, calculate significance & interpret results · no stats degree required</p>',
        unsafe_allow_html=True,
    )

    t = _t()
    tab1, tab2 = st.tabs(["📐  Sample size calculator", "📊  Results analyser"])

    # ── TAB 1: SAMPLE SIZE ─────────────────────────────────────────────────
    with tab1:
        st.markdown('<p class="section-label">Experiment parameters</p>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            baseline_cr = st.slider("Baseline conversion rate (%)", 0.5, 30.0, 3.2, 0.1) / 100
            mde         = st.slider("Minimum detectable effect (%)", 1.0, 50.0, 10.0, 0.5) / 100
        with c2:
            alpha = st.select_slider("Significance level (α)", options=[0.01, 0.05, 0.10], value=0.05)
            power = st.select_slider("Statistical power (1-β)", options=[0.70, 0.80, 0.90], value=0.80)

        daily_traffic = st.number_input(
            "Daily traffic to the test page", min_value=100, max_value=500_000, value=5000, step=500
        )

        n_per_variant = required_sample_size(baseline_cr, mde, alpha, power)
        total_n       = n_per_variant * 2
        runtime_days  = math.ceil(total_n / daily_traffic)
        target_cr     = baseline_cr * (1 + mde)

        st.markdown('<p class="section-label">Results</p>', unsafe_allow_html=True)
        r1, r2, r3, r4 = st.columns(4)
        with r1: st.metric("Users per variant", f"{n_per_variant:,}")
        with r2: st.metric("Total users needed", f"{total_n:,}")
        with r3: st.metric("Est. runtime",       f"{runtime_days} days")
        with r4: st.metric("Target CVR",         f"{target_cr*100:.2f}%")

        mde_range = np.linspace(0.02, 0.50, 50)
        ss_range  = [required_sample_size(baseline_cr, m, alpha, power) for m in mde_range]
        rt_range  = [math.ceil(s * 2 / daily_traffic) for s in ss_range]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=mde_range * 100, y=rt_range, mode="lines",
            line=dict(color=t["bar"], width=2),
            fill="tozeroy", fillcolor="rgba(59,130,246,0.07)",
        ))
        fig.add_vline(
            x=mde * 100, line_dash="dash", line_color="#f59e0b", line_width=1.5,
            annotation_text=f"Your MDE: {mde*100:.0f}%",
            annotation_position="top right",
            annotation_font_color=t["text"],
        )
        fig.update_layout(
            height=220, margin=dict(l=0, r=0, t=20, b=0),
            plot_bgcolor=t["plot_bg"], paper_bgcolor=t["paper"],
            font=dict(family="DM Sans", size=12, color=t["text"]),
            xaxis=dict(title="MDE (%)", showgrid=False,
                       tickfont=dict(color=t["text"]), title_font=dict(color=t["text"])),
            yaxis=dict(title="Runtime (days)", gridcolor=t["grid"],
                       tickfont=dict(color=t["text"]), title_font=dict(color=t["text"])),
        )
        st.markdown('<p class="section-label">Runtime vs MDE trade-off</p>', unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch")

    # ── TAB 2: RESULTS ─────────────────────────────────────────────────────
    with tab2:
        st.markdown('<p class="section-label">Enter your test results</p>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Control (A)**")
            n_control    = st.number_input("Visitors (Control)",    value=5240, key="nc")
            conv_control = st.number_input("Conversions (Control)", value=168,  key="cc")
        with c2:
            st.markdown("**Variant (B)**")
            n_variant    = st.number_input("Visitors (Variant)",    value=5190, key="nv")
            conv_variant = st.number_input("Conversions (Variant)", value=198,  key="cv")

        sig_level = st.select_slider(
            "Significance threshold", options=[0.01, 0.05, 0.10], value=0.05, key="sig2"
        )

        if st.button("Run significance test →", type="primary"):
            p_c, p_v, z, p_val, ci_low, ci_high = run_ztest(
                n_control, conv_control, n_variant, conv_variant
            )
            uplift = (p_v - p_c) / p_c * 100
            sig    = p_val < sig_level

            st.markdown('<p class="section-label">Test results</p>', unsafe_allow_html=True)
            r1, r2, r3, r4 = st.columns(4)
            with r1: st.metric("Control CVR", f"{p_c*100:.2f}%")
            with r2: st.metric("Variant CVR", f"{p_v*100:.2f}%")
            with r3: st.metric("Uplift",      f"{uplift:+.1f}%")
            with r4: st.metric("p-value",     f"{p_val:.4f}")

            if sig and uplift > 0:
                verdict = (
                    f"✅ <strong>Ship it.</strong> Variant B is statistically significant at α={sig_level}. "
                    f"Estimated uplift: <strong>{uplift:.1f}%</strong> "
                    f"(95% CI: {ci_low*100:+.2f}pp to {ci_high*100:+.2f}pp)."
                )
                box_cls = "success"
            elif sig and uplift < 0:
                verdict = "🚫 <strong>Do not ship.</strong> Variant B is significantly <em>worse</em> than control. Revert and investigate."
                box_cls = ""
            else:
                verdict = (
                    f"⏳ <strong>Inconclusive.</strong> p={p_val:.3f} doesn't meet α={sig_level}. "
                    "Run the test longer or increase traffic allocation."
                )
                box_cls = "warning"

            st.markdown(f'<div class="insight-box {box_cls}">{verdict}</div>', unsafe_allow_html=True)

            x    = np.linspace(-4, 4, 300)
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=x, y=stats.norm.pdf(x),
                fill="tozeroy", fillcolor="rgba(59,130,246,0.08)",
                line=dict(color=t["bar"]), name="Null distribution",
            ))
            fig2.add_vline(
                x=z, line_dash="dash", line_color=t["text"], line_width=1.5,
                annotation_text=f"z = {z:.2f}", annotation_position="top right",
                annotation_font_color=t["text"],
            )
            crit = stats.norm.ppf(1 - sig_level / 2)
            fig2.add_vrect(x0=crit, x1=4,   fillcolor="rgba(34,197,94,0.10)", line_width=0, annotation_text="Reject H₀")
            fig2.add_vrect(x0=-4, x1=-crit, fillcolor="rgba(34,197,94,0.10)", line_width=0)
            fig2.update_layout(
                height=220, margin=dict(l=0, r=0, t=10, b=0),
                plot_bgcolor=t["plot_bg"], paper_bgcolor=t["paper"],
                font=dict(family="DM Sans", size=12, color=t["text"]),
                xaxis=dict(title="z-score", showgrid=False,
                           tickfont=dict(color=t["text"]), title_font=dict(color=t["text"])),
                yaxis=dict(showgrid=False, showticklabels=False),
                showlegend=False,
            )
            st.markdown(
                '<p class="section-label">z-distribution · your test statistic</p>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(fig2, width="stretch")
