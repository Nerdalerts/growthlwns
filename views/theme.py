import streamlit as st

def is_dark() -> bool:
    return st.session_state.get("theme", "light") == "dark"

def plot_bg() -> str:
    return "#0f0f0f" if is_dark() else "#ffffff"

def paper_bg() -> str:
    return "#0f0f0f" if is_dark() else "#ffffff"

def grid_color() -> str:
    return "#2a2a2a" if is_dark() else "#eeeeee"

def font_color() -> str:
    return "#d0d0d0" if is_dark() else "#111111"

def axis_color() -> str:
    return "#444444" if is_dark() else "#cccccc"

def get_layout(**kwargs) -> dict:
    fc = font_color()
    gc = grid_color()
    bg = plot_bg()
    base = dict(
        plot_bgcolor=bg,
        paper_bgcolor=bg,
        font=dict(family="DM Sans", size=12, color=fc),
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(
            showgrid=False,
            color=fc,
            tickfont=dict(color=fc),
            linecolor=axis_color(),
            zerolinecolor=axis_color(),
        ),
        yaxis=dict(
            gridcolor=gc,
            color=fc,
            tickfont=dict(color=fc),
            linecolor=axis_color(),
            zerolinecolor=axis_color(),
        ),
    )
    # Deep merge kwargs so callers can override xaxis/yaxis partially
    for k, v in kwargs.items():
        if k in ("xaxis", "yaxis") and k in base and isinstance(v, dict):
            base[k] = {**base[k], **v}
        else:
            base[k] = v
    return base
