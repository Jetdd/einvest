"""Dashboard custom CSS + render helpers.

Inject GLOBAL_CSS once at app start via `st.markdown(GLOBAL_CSS,
unsafe_allow_html=True)`, then use the small helpers below to render
brand-styled cards, pills, and risk lights.
"""
from __future__ import annotations

GLOBAL_CSS = """
<style>
/* ────────────────────────────────────────────────────────────────────────
   Reset + typography
   ──────────────────────────────────────────────────────────────────────── */
:root {
  --bg:            #FFFFFF;
  --bg-elev:       #F6F8FB;
  --bg-card:       #FFFFFF;
  --bg-muted:      #FAFBFC;
  --border:        rgba(15, 23, 42, 0.08);
  --border-strong: rgba(15, 23, 42, 0.14);
  --text:          #0F172A;
  --text-muted:    #64748B;
  --text-subtle:   #94A3B8;
  --accent:        #2563EB;
  --accent-light:  #DBE7FF;
  --success:       #059669;
  --success-light: #D1FAE5;
  --warning:       #D97706;
  --warning-light: #FEF3C7;
  --danger:        #DC2626;
  --danger-light:  #FEE2E2;
  --shadow-sm:     0 1px 2px rgba(15, 23, 42, 0.04);
  --shadow:        0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04);
  --shadow-md:     0 4px 12px rgba(15, 23, 42, 0.06), 0 2px 4px rgba(15, 23, 42, 0.04);
  --radius:        10px;
  --radius-sm:     6px;
  --radius-lg:     14px;
}

html, body, [class*="stApp"] {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI',
               'PingFang SC', 'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
  font-feature-settings: 'cv02', 'cv03', 'cv04', 'cv11';
}

/* tighter container padding for desktop density */
.main .block-container {
  padding-top: 1.2rem;
  padding-bottom: 2.5rem;
  padding-left: 2.2rem;
  padding-right: 2.2rem;
  max-width: none;
}

/* hide Streamlit chrome */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] {
  background: transparent;
  height: 0;
}
.stDeployButton { display: none; }

/* default page title (h1) - tighten */
.main h1 {
  display: none;       /* we render a brand bar instead */
}

/* ────────────────────────────────────────────────────────────────────────
   Brand header
   ──────────────────────────────────────────────────────────────────────── */
.brand-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 0 18px 0;
  border-bottom: 1px solid var(--border);
  margin-bottom: 22px;
}
.brand-left { display: flex; align-items: center; gap: 14px; }
.brand-mark {
  width: 36px; height: 36px;
  border-radius: 9px;
  background: linear-gradient(135deg, #2563EB 0%, #1E40AF 100%);
  display: flex; align-items: center; justify-content: center;
  color: white; font-weight: 800; font-size: 17px;
  letter-spacing: -0.02em;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
}
.brand-name {
  font-size: 18px; font-weight: 700; letter-spacing: -0.02em;
  color: var(--text);
}
.brand-name span { color: var(--accent); font-weight: 800; }
.brand-tag {
  font-size: 11px; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.12em;
  margin-top: 1px;
}
.brand-right {
  display: flex; align-items: center; gap: 22px;
  color: var(--text-muted); font-size: 13px;
}
.brand-meta { display: flex; flex-direction: column; align-items: flex-end; }
.brand-meta-label {
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em;
  color: var(--text-subtle);
}
.brand-meta-value {
  font-size: 14px; font-weight: 600; color: var(--text);
  font-variant-numeric: tabular-nums;
}

/* ────────────────────────────────────────────────────────────────────────
   KPI / metric cards
   ──────────────────────────────────────────────────────────────────────── */
.kpi-grid {
  display: grid;
  gap: 14px;
  margin-bottom: 18px;
}
.kpi-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
  box-shadow: var(--shadow-sm);
  transition: box-shadow 160ms ease, border-color 160ms ease;
}
.kpi-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--border-strong);
}
.kpi-card.accent { border-color: var(--accent-light); background: linear-gradient(180deg, #F5F8FF 0%, #FFFFFF 60%); }
.kpi-label {
  font-size: 10.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin-bottom: 8px;
  display: flex; align-items: center; gap: 6px;
}
.kpi-value {
  font-size: 26px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--text);
  letter-spacing: -0.02em;
  line-height: 1.1;
}
.kpi-value.sm { font-size: 20px; }
.kpi-value.xl { font-size: 32px; }
.kpi-delta {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 6px;
  font-weight: 500;
}
.kpi-delta.up { color: var(--success); }
.kpi-delta.down { color: var(--danger); }
.kpi-delta.muted { color: var(--text-subtle); }

/* ────────────────────────────────────────────────────────────────────────
   Status pills + risk lights
   ──────────────────────────────────────────────────────────────────────── */
.pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 13px; font-weight: 600;
  line-height: 1.5;
  border: 1px solid transparent;
}
.pill.lg { font-size: 15px; padding: 6px 16px; }
.pill.xl { font-size: 17px; padding: 8px 20px; }
.pill-success { background: var(--success-light); color: var(--success); border-color: rgba(5, 150, 105, 0.2); }
.pill-warning { background: var(--warning-light); color: var(--warning); border-color: rgba(217, 119, 6, 0.2); }
.pill-danger  { background: var(--danger-light);  color: var(--danger);  border-color: rgba(220, 38, 38, 0.2); }
.pill-accent  { background: var(--accent-light);  color: var(--accent);  border-color: rgba(37, 99, 235, 0.2); }
.pill-muted   { background: #F1F5F9;              color: var(--text-muted); border-color: var(--border); }

/* risk dot */
.dot {
  display: inline-block;
  width: 10px; height: 10px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
.dot-green  { background: var(--success); box-shadow: 0 0 0 4px rgba(5, 150, 105, 0.15); }
.dot-yellow { background: var(--warning); box-shadow: 0 0 0 4px rgba(217, 119, 6, 0.15); }
.dot-red    { background: var(--danger);  box-shadow: 0 0 0 4px rgba(220, 38, 38, 0.15); }
.dot-grey   { background: #94A3B8; }

/* ────────────────────────────────────────────────────────────────────────
   Section header
   ──────────────────────────────────────────────────────────────────────── */
.section-h {
  display: flex; align-items: baseline; gap: 10px;
  margin: 26px 0 12px 0;
}
.section-h::before {
  content: "";
  width: 3px; height: 16px; background: var(--accent);
  border-radius: 2px; align-self: center;
}
.section-h .section-title {
  font-size: 14px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--text);
}
.section-h .section-sub {
  font-size: 12px; color: var(--text-muted);
}

/* ────────────────────────────────────────────────────────────────────────
   Progress bars (replace st.progress styling)
   ──────────────────────────────────────────────────────────────────────── */
.progress-row { margin-bottom: 12px; }
.progress-label {
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 12px; color: var(--text-muted); margin-bottom: 5px;
}
.progress-label .pl-name { font-weight: 600; color: var(--text); font-size: 13px; }
.progress-label .pl-value { font-variant-numeric: tabular-nums; font-weight: 600; color: var(--text); }
.progress-track {
  width: 100%; height: 8px;
  background: #EEF2F7;
  border-radius: 4px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 250ms ease;
}
.progress-fill.accent  { background: linear-gradient(90deg, #3B82F6 0%, #2563EB 100%); }
.progress-fill.success { background: linear-gradient(90deg, #34D399 0%, #059669 100%); }
.progress-fill.warning { background: linear-gradient(90deg, #FBBF24 0%, #D97706 100%); }
.progress-fill.danger  { background: linear-gradient(90deg, #F87171 0%, #DC2626 100%); }

/* ────────────────────────────────────────────────────────────────────────
   Streamlit native polish
   ──────────────────────────────────────────────────────────────────────── */

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
  gap: 0;
  border-bottom: 1px solid var(--border);
}
.stTabs [data-baseweb="tab"] {
  background: transparent;
  padding: 10px 18px;
  font-weight: 500;
  color: var(--text-muted);
  border-radius: 0;
  border-bottom: 2px solid transparent;
  transition: color 120ms ease, border-color 120ms ease;
}
.stTabs [data-baseweb="tab"]:hover {
  color: var(--text);
  background: var(--bg-muted);
}
.stTabs [aria-selected="true"] {
  color: var(--accent) !important;
  border-bottom-color: var(--accent) !important;
  font-weight: 600;
}

/* Native metric (we keep a few of these around for fallback) */
[data-testid="stMetric"] {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
  box-shadow: var(--shadow-sm);
}
[data-testid="stMetric"] [data-testid="stMetricLabel"] {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
  color: var(--text-muted);
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
  font-size: 26px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}
[data-testid="stMetric"] [data-testid="stMetricDelta"] {
  font-size: 12px;
}

/* Sidebar */
[data-testid="stSidebar"] {
  background: var(--bg-elev);
  border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] > div:first-child {
  padding-top: 1rem;
}
[data-testid="stSidebar"] [data-testid="stMetric"] {
  background: var(--bg-card);
}
[data-testid="stSidebar"] h2 {
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  font-weight: 700;
  margin-bottom: 0.6rem;
}

.sidebar-brand {
  display: flex; align-items: center; gap: 10px;
  padding: 4px 0 16px 0;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--border);
}
.sidebar-brand .brand-mark { width: 30px; height: 30px; font-size: 14px; }
.sidebar-brand .name { font-weight: 700; color: var(--text); letter-spacing: -0.02em; }
.sidebar-brand .tag {
  font-size: 10px; color: var(--text-subtle); text-transform: uppercase;
  letter-spacing: 0.1em;
}

/* DataFrame */
.stDataFrame {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

/* Headings inside tabs */
.stTabs h3, .stTabs h4 {
  letter-spacing: -0.01em;
  color: var(--text);
}

/* Captions */
.stCaption, .stMarkdown small, [data-testid="stCaptionContainer"] {
  color: var(--text-subtle);
  font-size: 12px;
}

/* Buttons */
.stButton > button {
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-strong);
  font-weight: 600;
  color: var(--text);
  background: var(--bg-card);
  transition: all 120ms ease;
}
.stButton > button:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-light);
}

/* Divider — softer */
hr {
  border: none;
  border-top: 1px solid var(--border);
  margin: 1.4rem 0;
}

/* dataframe alternating row */
.stDataFrame table tbody tr:nth-child(even) td { background: #FAFBFC; }
</style>
"""


# ──────────────────────────────────────────────────────────────────────────
# Render helpers — return HTML strings, caller passes to st.markdown(...,
# unsafe_allow_html=True). Helpers return strings rather than rendering
# directly so they can be composed inside columns / grids.
# ──────────────────────────────────────────────────────────────────────────

def kpi_card(label: str, value: str, *, delta: str | None = None,
              delta_kind: str = "muted", accent: bool = False,
              icon: str | None = None, value_size: str = "") -> str:
    """One KPI card. `delta_kind` ∈ up|down|muted. `value_size` ∈ ""|sm|xl."""
    icon_html = f'<span>{icon}</span>' if icon else ""
    delta_html = (f'<div class="kpi-delta {delta_kind}">{delta}</div>'
                  if delta else "")
    size_class = f" {value_size}" if value_size else ""
    accent_cls = " accent" if accent else ""
    return (
        f'<div class="kpi-card{accent_cls}">'
        f'<div class="kpi-label">{icon_html}{label}</div>'
        f'<div class="kpi-value{size_class}">{value}</div>'
        f'{delta_html}'
        f'</div>'
    )


def pill(text: str, kind: str = "muted", size: str = "") -> str:
    """`kind` ∈ success|warning|danger|accent|muted. `size` ∈ ""|lg|xl."""
    size_cls = f" {size}" if size else ""
    return f'<span class="pill pill-{kind}{size_cls}">{text}</span>'


_RISK_TO_DOT = {"绿": "green", "黄": "yellow", "红": "red"}


def risk_dot(level: str) -> str:
    color = _RISK_TO_DOT.get(level, "grey")
    return f'<span class="dot dot-{color}"></span>'


def progress_row(name: str, value: float, *, sub: str | None = None,
                  total: float = 100.0, kind: str = "accent") -> str:
    """Horizontal progress bar with label + value. `kind` ∈ accent|success|warning|danger."""
    pct = max(0.0, min(100.0, value / total * 100))
    sub_html = (f'<span class="pl-value">{value:.0f}/100 '
                f'<span style="color:#94A3B8;font-weight:500"> · {sub}</span></span>'
                if sub else f'<span class="pl-value">{value:.0f}/100</span>')
    return (
        f'<div class="progress-row">'
        f'<div class="progress-label">'
        f'<span class="pl-name">{name}</span>{sub_html}'
        f'</div>'
        f'<div class="progress-track"><div class="progress-fill {kind}" '
        f'style="width:{pct:.1f}%"></div></div>'
        f'</div>'
    )


def section_header(title: str, sub: str | None = None) -> str:
    sub_html = f'<span class="section-sub">{sub}</span>' if sub else ""
    return (
        f'<div class="section-h">'
        f'<span class="section-title">{title}</span>{sub_html}'
        f'</div>'
    )


def brand_bar(*, name: str = "einvest", subname: str = "TERMINAL",
               trade_date: str = "—", n_stocks: int = 0, n_themes: int = 0,
               state: str | None = None, state_kind: str = "muted") -> str:
    """Top brand header with trade-date / universe stats / state pill."""
    state_html = (f'<span class="pill pill-{state_kind} lg" '
                  f'style="margin-left:18px">{state}</span>'
                  if state else "")
    return (
        f'<div class="brand-bar">'
        f'<div class="brand-left">'
        f'<div class="brand-mark">e</div>'
        f'<div>'
        f'<div class="brand-name">{name} <span>{subname}</span></div>'
        f'<div class="brand-tag">A-share Mid-term Decision System</div>'
        f'</div>'
        f'{state_html}'
        f'</div>'
        f'<div class="brand-right">'
        f'<div class="brand-meta"><span class="brand-meta-label">Trade Date</span>'
        f'<span class="brand-meta-value">{trade_date}</span></div>'
        f'<div class="brand-meta"><span class="brand-meta-label">Stocks</span>'
        f'<span class="brand-meta-value">{n_stocks:,}</span></div>'
        f'<div class="brand-meta"><span class="brand-meta-label">Themes</span>'
        f'<span class="brand-meta-value">{n_themes}</span></div>'
        f'</div>'
        f'</div>'
    )


def sidebar_brand() -> str:
    return (
        f'<div class="sidebar-brand">'
        f'<div class="brand-mark">e</div>'
        f'<div>'
        f'<div class="name">einvest</div>'
        f'<div class="tag">Terminal · v0.1</div>'
        f'</div>'
        f'</div>'
    )
