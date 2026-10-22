from dotenv import load_dotenv
import streamlit as st

load_dotenv()

st.set_page_config(
    page_title="GrowthLens",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------
# Theme state (read by theme.py's is_dark() / get_layout() too — same key)
# ------------------------------------------------------------------
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

if "current_page" not in st.session_state:
    st.session_state.current_page = "🏠  North Star Dashboard"

NAV_OPTIONS = [
    "🏠  North Star Dashboard",
    "🔽  Funnel Analysis",
    "🔁  Cohort Retention",
    "🧪  A/B Test Engine",
    "💰  Revenue Analytics",
    "👥  RFM Segmentation",
    "📦  Product Analytics",
    "💬  Ask Copilot",
    "📊  Copilot Admin",
]

THEMES = {
    "light": {
        "bg": "#ffffff",
        "bg-alt": "#f9f9f7",
        "panel": "#ffffff",
        "border": "#ececec",
        "text": "#111111",
        "text-muted": "#888888",
        "text-faint": "#aaaaaa",
        "sidebar-bg": "#0f0f0f",
        "sidebar-text": "#e5e5e5",
        "sidebar-text-muted": "#9a9a9a",
        "sidebar-active-bg": "#2563eb",
        "accent": "#3b82f6",
        "insight-bg": "#f0f7ff",
        "insight-text": "#1e40af",
        "warning-bg": "#fffbeb",
        "warning-text": "#92400e",
        "warning-border": "#f59e0b",
        "success-bg": "#f0fdf4",
        "success-text": "#166534",
        "success-border": "#22c55e",
        "shadow": "0 1px 3px rgba(0,0,0,0.04)",
        "shadow-hover": "0 4px 14px rgba(0,0,0,0.08)",
    },
    "dark": {
        "bg": "#0f0f0f",
        "bg-alt": "#1a1a1a",
        "panel": "#1a1a1a",
        "border": "#2a2a2a",
        "text": "#e8e8e8",
        "text-muted": "#9a9a9a",
        "text-faint": "#777777",
        "sidebar-bg": "#0a0a0a",
        "sidebar-text": "#e5e5e5",
        "sidebar-text-muted": "#8a8a8a",
        "sidebar-active-bg": "#2563eb",
        "accent": "#5b9bff",
        "insight-bg": "#12233f",
        "insight-text": "#8fbcff",
        "warning-bg": "#3a2c0f",
        "warning-text": "#f3c674",
        "warning-border": "#f59e0b",
        "success-bg": "#0f2e1c",
        "success-text": "#7ee2a8",
        "success-border": "#22c55e",
        "shadow": "0 1px 3px rgba(0,0,0,0.4)",
        "shadow-hover": "0 4px 18px rgba(0,0,0,0.6)",
    },
}

t = THEMES[st.session_state.theme]

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

:root {{
    --bg: {t['bg']}; --bg-alt: {t['bg-alt']}; --panel: {t['panel']}; --border: {t['border']};
    --text: {t['text']}; --text-muted: {t['text-muted']}; --text-faint: {t['text-faint']};
    --sidebar-bg: {t['sidebar-bg']}; --sidebar-text: {t['sidebar-text']};
    --sidebar-text-muted: {t['sidebar-text-muted']}; --sidebar-active-bg: {t['sidebar-active-bg']};
    --accent: {t['accent']}; --insight-bg: {t['insight-bg']}; --insight-text: {t['insight-text']};
    --warning-bg: {t['warning-bg']}; --warning-text: {t['warning-text']}; --warning-border: {t['warning-border']};
    --success-bg: {t['success-bg']}; --success-text: {t['success-text']}; --success-border: {t['success-border']};
    --shadow: {t['shadow']}; --shadow-hover: {t['shadow-hover']};
}}

html, body, [class*="css"] {{ font-family: 'DM Sans', sans-serif; }}

.stApp {{ background: var(--bg); color: var(--text); }}

/* Only hide the app-menu and footer branding. Never touch `header` —
   Streamlit's sidebar expand/collapse control lives inside it, and
   hiding the header is what breaks the sidebar permanently. Leave the
   native collapse behaviour completely alone; it works out of the box. */
#MainMenu, footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}

/* ---- Sidebar ---- */
[data-testid="stSidebar"] {{
    background: var(--sidebar-bg);
    border-right: 1px solid rgba(255,255,255,0.06);
}}
[data-testid="stSidebar"] * {{ color: var(--sidebar-text) !important; }}

.sidebar-brand {{ font-size: 17px; font-weight: 600; letter-spacing: -0.01em; margin-bottom: 2px; }}
.sidebar-tagline {{ font-size: 12px; color: var(--sidebar-text-muted) !important; margin-bottom: 18px; }}
.sidebar-divider {{ border: none; border-top: 1px solid rgba(255,255,255,0.08); margin: 14px 0; }}
.sidebar-footnote {{ font-size: 11px; line-height: 1.7; color: var(--sidebar-text-muted) !important; }}

/* Nav radio styled as a clean, high-contrast menu list */
[data-testid="stSidebar"] .stRadio > div {{ gap: 3px; }}
[data-testid="stSidebar"] .stRadio label {{
    font-size: 14px !important;
    padding: 9px 12px;
    border-radius: 8px;
    width: 100%;
    transition: background 0.15s ease;
}}
[data-testid="stSidebar"] .stRadio label:hover {{ background: rgba(255,255,255,0.08); }}
[data-testid="stSidebar"] .stRadio label:has(input:checked) {{
    background: var(--sidebar-active-bg);
}}
[data-testid="stSidebar"] .stRadio label p {{ font-size: 14px !important; }}

/* Theme toggle buttons */
[data-testid="stSidebar"] button {{
    border-radius: 8px !important;
    font-size: 12.5px !important;
    transition: background 0.15s ease, border-color 0.15s ease;
}}
[data-testid="stSidebar"] button[kind="secondary"] {{
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: var(--sidebar-text) !important;
}}
[data-testid="stSidebar"] button[kind="secondary"]:hover {{
    background: rgba(255,255,255,0.14) !important;
    border-color: rgba(255,255,255,0.2) !important;
}}
[data-testid="stSidebar"] button[kind="primary"] {{
    background: var(--accent) !important;
    border: 1px solid var(--accent) !important;
    color: #ffffff !important;
}}

/* ---- Metric cards ---- */
[data-testid="stMetric"] {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem 1.25rem;
    box-shadow: var(--shadow);
    transition: box-shadow 0.2s ease, transform 0.2s ease;
}}
[data-testid="stMetric"]:hover {{ box-shadow: var(--shadow-hover); transform: translateY(-1px); }}
[data-testid="stMetricLabel"] {{
    font-size: 12px !important; color: var(--text-muted) !important;
    text-transform: uppercase; letter-spacing: 0.05em;
}}
[data-testid="stMetricValue"] {{ font-size: 26px !important; font-weight: 600 !important; color: var(--text) !important; }}
[data-testid="stMetricDelta"] {{ color: var(--text-muted) !important; }}

/* ---- General content surfaces ---- */
[data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; border: 1px solid var(--border); }}
.block-container {{ padding-top: 2rem; }}

/* Tabs */
[data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid var(--border); }}
[data-baseweb="tab"] {{ color: var(--text-muted) !important; }}
[aria-selected="true"][data-baseweb="tab"] {{ color: var(--accent) !important; }}

/* Inputs */
.stTextInput input, .stNumberInput input {{
    background: var(--panel) !important;
    color: var(--text) !important;
    border-color: var(--border) !important;
}}

/* Select / multiselect closed control */
div[data-baseweb="select"] > div {{
    background: var(--panel) !important;
    border-color: var(--border) !important;
}}
div[data-baseweb="select"] input {{ color: var(--text) !important; }}
div[data-baseweb="select"] svg {{ fill: var(--text-muted) !important; }}

/* Selected option pills (tags) — including the "x" remove icon, which
   was invisible before because it kept its default dark fill against
   our now-dark pill background. That's what made removing options
   feel broken: the click target existed but you couldn't see it. */
span[data-baseweb="tag"] {{ background: var(--accent) !important; }}
span[data-baseweb="tag"] span {{ color: #ffffff !important; }}
span[data-baseweb="tag"] svg {{ fill: #ffffff !important; opacity: 0.85; }}
span[data-baseweb="tag"] svg:hover {{ opacity: 1; }}

/* Dropdown option list (rendered in a portal, so it needs its own
   explicit styling rather than inheriting from the control above) */
div[data-baseweb="popover"] ul {{ background: var(--panel) !important; }}
div[data-baseweb="popover"] li {{ color: var(--text) !important; }}
div[data-baseweb="popover"] li:hover {{ background: var(--bg-alt) !important; }}

.page-title {{ font-size: 22px; font-weight: 600; color: var(--text); margin-bottom: 4px; }}
.page-subtitle {{ font-size: 14px; color: var(--text-muted); margin-bottom: 1.5rem; }}
.section-label {{
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.08em; color: var(--text-faint); margin: 1.5rem 0 0.75rem;
}}

.insight-box {{
    background: var(--insight-bg); border-left: 3px solid var(--accent);
    border-radius: 0 8px 8px 0; padding: 0.75rem 1rem; font-size: 13px;
    color: var(--insight-text); margin: 1rem 0;
}}
.insight-box.warning {{ background: var(--warning-bg); border-left-color: var(--warning-border); color: var(--warning-text); }}
.insight-box.success {{ background: var(--success-bg); border-left-color: var(--success-border); color: var(--success-text); }}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="sidebar-brand">🔭 GrowthLens</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-tagline">E-commerce Analytics Suite</div>', unsafe_allow_html=True)
    st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)

    st.radio(
        "Navigation",
        NAV_OPTIONS,
        label_visibility="collapsed",
        key="current_page",
    )

    st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)

    light_col, dark_col = st.columns(2)
    with light_col:
        label = "☀️ Light ✓" if st.session_state.theme == "light" else "☀️ Light"
        if st.button(label, use_container_width=True, key="light_btn",
                     type="primary" if st.session_state.theme == "light" else "secondary"):
            st.session_state.theme = "light"
            st.rerun()
    with dark_col:
        label = "🌙 Dark ✓" if st.session_state.theme == "dark" else "🌙 Dark"
        if st.button(label, use_container_width=True, key="dark_btn",
                     type="primary" if st.session_state.theme == "dark" else "secondary"):
            st.session_state.theme = "dark"
            st.rerun()

    st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)
    st.markdown(
        '<div class="sidebar-footnote">Data: Synthetic DTC dataset<br>'
        '12-month rolling window<br>~45,000 simulated orders</div>',
        unsafe_allow_html=True,
    )

page = st.session_state.current_page

# --- Route pages ---
if "North Star" in page:
    from views import north_star
    north_star.render()
elif "Funnel" in page:
    from views import funnel
    funnel.render()
elif "Cohort" in page:
    from views import cohort
    cohort.render()
elif "A/B" in page:
    from views import ab_test
    ab_test.render()
elif "Revenue" in page:
    from views import revenue
    revenue.render()
elif "RFM" in page:
    from views import rfm
    rfm.render()
elif "Product Analytics" in page:
    from views import product_analytics
    product_analytics.render()
elif "Ask Copilot" in page:
    from pages import Ask
    Ask.render()
elif "Copilot Admin" in page:
    from pages import Admin
    Admin.render()
