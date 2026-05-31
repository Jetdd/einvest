"""Dashboard CSS + render helpers — Bloomberg-dark theme.

Aesthetic:
- Deep background (#0B0E14) · light text (#E8ECF1) · amber accent (#FFB000)
- 红涨绿跌 (CN convention): up = red, down = green
- Inter for text · JetBrains Mono for numerics
- Minimal chrome: thin borders, no shadows/gradients, sharp corners

Inject GLOBAL_CSS once at app start via `st.markdown(GLOBAL_CSS,
unsafe_allow_html=True)`, then use the small helpers below to render
brand-styled cards, pills, and risk lights.
"""
from __future__ import annotations

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ────────────────────────────────────────────────────────────────────────
   Palette (Bloomberg-dark)
   ──────────────────────────────────────────────────────────────────────── */
:root {
  --bg:            #0B0E14;
  --bg-elev:       #14181F;
  --bg-card:       #14181F;
  --bg-muted:      #1C2129;
  --bg-hover:      #1F2530;
  --border:        #232830;
  --border-strong: #2E343F;
  --text:          #E8ECF1;
  --text-muted:    #9BA4B0;
  --text-subtle:   #5F6877;
  --accent:        #FFB000;          /* amber */
  --accent-dim:    #B07700;
  --accent-bg:     #2A2105;
  /* 红涨绿跌 (CN) */
  --up:            #E63946;          /* red — positive return */
  --up-bg:         #2A1414;
  --up-dim:        #8B1F26;
  --down:          #06A77D;          /* green — negative return */
  --down-bg:       #0D2418;
  --down-dim:      #045949;
  /* state */
  --warning:       #FFB000;
  --danger:        #E63946;
  --success:       #06A77D;
  --info:          #4A8FE7;
  --info-bg:       #0F1B2E;
  --radius:        3px;
  --radius-sm:     2px;
}

/* ────────────────────────────────────────────────────────────────────────
   Global typography + Streamlit base
   ──────────────────────────────────────────────────────────────────────── */
html, body, [class*="stApp"] {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI',
               'PingFang SC', 'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
  background: var(--bg);
  color: var(--text);
  font-feature-settings: 'cv02', 'cv03', 'cv04', 'cv11';
}

/* numerical text everywhere we mark with .num or in our kpi values */
.num, .kpi-value, .kpi-delta, .brand-meta-value,
.progress-label .pl-value, .progress-label .pl-name,
[data-testid="stMetricValue"], [data-testid="stMetricDelta"] {
  font-family: 'JetBrains Mono', 'IBM Plex Mono', 'Consolas', monospace;
  font-variant-numeric: tabular-nums;
}

/* tight container padding */
.main .block-container {
  padding-top: 0.8rem;
  padding-bottom: 2rem;
  padding-left: 1.8rem;
  padding-right: 1.8rem;
  max-width: none;
}

/* hide Streamlit chrome */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; height: 0; }
.stDeployButton { display: none; }
.main h1 { display: none; }

/* selection */
::selection { background: var(--accent-bg); color: var(--accent); }

/* scrollbar (webkit) */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: #404856; }

/* ────────────────────────────────────────────────────────────────────────
   Brand bar
   ──────────────────────────────────────────────────────────────────────── */
.brand-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0 14px 0;
  border-bottom: 1px solid var(--border-strong);
  margin-bottom: 14px;
}
.brand-left { display: flex; align-items: center; gap: 16px; }
.brand-mark { display: none; }       /* drop the rounded-square mark */
.brand-name {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.18em;
  color: var(--text);
  text-transform: uppercase;
}
.brand-name span {
  color: var(--accent);
  font-weight: 700;
  margin-left: 4px;
  letter-spacing: 0.2em;
}
.brand-tag {
  font-size: 10px;
  color: var(--text-subtle);
  text-transform: uppercase;
  letter-spacing: 0.14em;
  margin-top: 3px;
}
.brand-right {
  display: flex; align-items: center; gap: 26px;
}
.brand-meta { display: flex; flex-direction: column; align-items: flex-end; }
.brand-meta-label {
  font-size: 9.5px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--text-subtle);
  font-family: 'Inter', sans-serif;
}
.brand-meta-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

/* ────────────────────────────────────────────────────────────────────────
   KPI cards
   ──────────────────────────────────────────────────────────────────────── */
.kpi-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 14px;
  transition: border-color 120ms ease;
}
.kpi-card:hover { border-color: var(--border-strong); }
.kpi-card.accent {
  border-left: 2px solid var(--accent);
}
.kpi-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--text-subtle);
  margin-bottom: 8px;
  display: flex; align-items: center; gap: 6px;
}
.kpi-value {
  font-size: 22px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.005em;
  line-height: 1.1;
}
.kpi-value.sm { font-size: 16px; }
.kpi-value.xl { font-size: 28px; font-weight: 700; }
.kpi-value.xxl { font-size: 44px; font-weight: 800; letter-spacing: -0.02em; }
/* emphasized hero card — for 建议仓位 */
.kpi-card.hero {
  padding: 18px 20px;
  background: linear-gradient(180deg, rgba(255,176,0,0.07), rgba(255,176,0,0.015));
  border: 1px solid var(--accent-dim);
  border-left: 3px solid var(--accent);
}
.kpi-delta {
  font-size: 11px;
  color: var(--text-subtle);
  margin-top: 6px;
  font-weight: 500;
}
.kpi-delta.up { color: var(--up); }
.kpi-delta.down { color: var(--down); }
.kpi-delta.muted { color: var(--text-subtle); }

/* ────────────────────────────────────────────────────────────────────────
   Pills (outlined, terminal style)
   ──────────────────────────────────────────────────────────────────────── */
.pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
  line-height: 1.5;
  letter-spacing: 0.04em;
  border: 1px solid currentColor;
  background: transparent;
  text-transform: uppercase;
  font-family: 'Inter', sans-serif;
}
.pill.lg { font-size: 13px; padding: 3px 10px; }
.pill.xl { font-size: 15px; padding: 5px 14px; }
.pill-success { color: var(--success); }
.pill-warning { color: var(--warning); }
.pill-danger  { color: var(--danger); }
.pill-accent  { color: var(--accent); }
.pill-muted   { color: var(--text-muted); }

/* risk dot */
.dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
.dot-green  { background: var(--success); }
.dot-yellow { background: var(--warning); }
.dot-red    { background: var(--danger); }
.dot-grey   { background: var(--text-subtle); }

/* ────────────────────────────────────────────────────────────────────────
   Section header
   ──────────────────────────────────────────────────────────────────────── */
.section-h {
  display: flex; align-items: baseline; gap: 12px;
  margin: 28px 0 13px 0;
  padding: 0 0 7px 11px;
  border-bottom: 1px solid var(--border-strong);
  position: relative;
}
.section-h::before {
  content: "";
  position: absolute; left: 0; top: 2px; bottom: 8px;
  width: 3px; border-radius: 2px;
  background: var(--accent);
}
.section-h .section-title {
  font-size: 15px; font-weight: 800;
  text-transform: uppercase; letter-spacing: 0.13em;
  color: var(--text);
}
.section-h .section-sub {
  font-size: 10px;
  color: var(--text-subtle);
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

/* ────────────────────────────────────────────────────────────────────────
   Progress bar (kept for compatibility — flat, no gradient)
   ──────────────────────────────────────────────────────────────────────── */
.progress-row { margin-bottom: 12px; }
.progress-label {
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 12px; color: var(--text-muted); margin-bottom: 5px;
}
.progress-label .pl-name { font-weight: 600; color: var(--text); font-size: 12px; }
.progress-label .pl-value { font-weight: 600; color: var(--text); font-size: 12px; }
.progress-track {
  width: 100%; height: 4px;
  background: var(--bg-muted);
  border-radius: 0;
  overflow: hidden;
}
.progress-fill { height: 100%; border-radius: 0; }
.progress-fill.accent  { background: var(--accent); }
.progress-fill.success { background: var(--success); }
.progress-fill.warning { background: var(--warning); }
.progress-fill.danger  { background: var(--danger); }

/* ────────────────────────────────────────────────────────────────────────
   Streamlit native overrides
   ──────────────────────────────────────────────────────────────────────── */

/* Tabs — terminal-style */
.stTabs [data-baseweb="tab-list"] {
  gap: 0;
  border-bottom: 1px solid var(--border);
  background: transparent;
}
.stTabs [data-baseweb="tab"] {
  background: transparent;
  padding: 9px 18px;
  font-weight: 600;
  font-size: 11.5px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
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
}

/* Native metric */
[data-testid="stMetric"] {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 14px;
}
[data-testid="stMetric"] [data-testid="stMetricLabel"] {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-weight: 600;
  color: var(--text-subtle);
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
  font-size: 22px;
  font-weight: 600;
  color: var(--text);
}
[data-testid="stMetric"] [data-testid="stMetricDelta"] {
  font-size: 11px;
}

/* Sidebar */
[data-testid="stSidebar"] {
  background: var(--bg-elev);
  border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] > div:first-child { padding-top: 1rem; }
[data-testid="stSidebar"] [data-testid="stMetric"] { background: var(--bg-card); }
[data-testid="stSidebar"] h2 {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--text-subtle);
  font-weight: 700;
  margin-bottom: 0.6rem;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p { color: var(--text-muted); }

.sidebar-brand {
  display: flex; align-items: center; gap: 10px;
  padding: 2px 0 14px 0;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--border);
}
.sidebar-brand .brand-mark { display: none; }
.sidebar-brand .name {
  font-weight: 700; color: var(--text);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-size: 13px;
}
.sidebar-brand .tag {
  font-size: 9.5px; color: var(--text-subtle);
  text-transform: uppercase; letter-spacing: 0.12em;
}

/* DataFrame */
.stDataFrame {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.stDataFrame table { background: var(--bg-card); color: var(--text); }
.stDataFrame thead th {
  background: var(--bg-muted) !important;
  color: var(--text-muted) !important;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  border-bottom: 1px solid var(--border-strong) !important;
}
.stDataFrame tbody td {
  font-size: 12.5px;
  border-bottom: 1px solid var(--border) !important;
}
.stDataFrame tbody tr:hover td { background: var(--bg-hover) !important; }

/* Headings inside tabs */
.stTabs h3, .stTabs h4 {
  letter-spacing: 0.04em;
  color: var(--text);
  font-weight: 600;
}

/* Captions */
.stCaption, .stMarkdown small, [data-testid="stCaptionContainer"] {
  color: var(--text-subtle);
  font-size: 11.5px;
  font-style: normal;
}

/* Buttons */
.stButton > button {
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-strong);
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text);
  background: var(--bg-card);
  transition: border-color 120ms ease, color 120ms ease;
}
.stButton > button:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--bg-card);
}

/* Inputs */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-baseweb="select"] > div {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  color: var(--text) !important;
  border-radius: var(--radius-sm) !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 12.5px !important;
}
[data-testid="stTextInput"] input:focus { border-color: var(--accent) !important; }

/* Multiselect tags */
[data-baseweb="tag"] {
  background: var(--accent-bg) !important;
  color: var(--accent) !important;
  border-radius: var(--radius-sm) !important;
  font-size: 11.5px !important;
  font-weight: 600 !important;
}

/* Slider */
[data-baseweb="slider"] [role="slider"] { background: var(--accent) !important; }
[data-baseweb="slider"] [data-testid="stTickBar"] { color: var(--text-subtle); }

/* Expander */
[data-testid="stExpander"] {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
[data-testid="stExpander"] summary {
  font-size: 11.5px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  font-weight: 600;
}
[data-testid="stExpander"] summary:hover { color: var(--accent); }

/* Divider */
hr {
  border: none;
  border-top: 1px solid var(--border);
  margin: 1.2rem 0;
}

/* Info / warning / error boxes */
[data-testid="stAlert"] {
  background: var(--bg-muted);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
}

/* Plotly chart container background */
.js-plotly-plot, .plotly { background: transparent !important; }
.user-select-none.svg-container { background: transparent !important; }

/* ────────────────────────────────────────────────────────────────────────
   Industry chain (产业链图谱)
   ──────────────────────────────────────────────────────────────────────── */
.chain { margin: 6px 0 2px; }
.tier-row { display: flex; align-items: stretch; gap: 12px; margin: 5px 0; }
.tier-tag {
  flex: 0 0 42px; display: flex; align-items: center; justify-content: center;
  writing-mode: vertical-rl; text-orientation: upright;
  background: var(--bg-muted); border: 1px solid var(--border);
  border-radius: 4px; font-weight: 800; font-size: 13px; letter-spacing: 0.35em;
  color: var(--text-muted);
}
.seg-wrap { flex: 1; display: flex; gap: 10px; flex-wrap: wrap; }
.seg-card {
  flex: 1 1 200px; min-width: 178px;
  border: 1px solid var(--border); border-radius: 5px; padding: 9px 11px;
  transition: border-color 120ms ease;
}
.seg-card:hover { border-color: var(--border-strong); }
.seg-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.seg-name { font-weight: 700; font-size: 13px; color: var(--text); }
.seg-ret { font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 12.5px; }
.seg-sub {
  font-size: 9.5px; color: var(--text-subtle); margin: 3px 0 7px;
  letter-spacing: 0.02em; text-transform: uppercase;
}
.seg-chips { display: flex; flex-wrap: wrap; gap: 5px; }
.chain-chip {
  font-size: 11px; padding: 2px 7px; border-radius: 3px;
  background: var(--bg-muted); border: 1px solid var(--border);
  color: #C9D2DC; font-weight: 500; white-space: nowrap;
}
.chain-chip .cp { font-family: 'JetBrains Mono', monospace; font-weight: 600; }
.tier-arrow {
  text-align: center; color: var(--text-subtle); font-size: 11px;
  margin: -1px 0; padding-left: 42px; letter-spacing: 0.4em;
}

/* ────────────────────────────────────────────────────────────────────────
   Cycle-phase rail (周期阶段 horizontal stepper)
   ──────────────────────────────────────────────────────────────────────── */
.cycle-rail {
  display: flex; justify-content: space-between; align-items: flex-start;
  position: relative; padding: 10px 6px 4px;
}
.cycle-rail::before {
  content: ""; position: absolute; top: 15px; left: 18px; right: 18px;
  height: 2px; background: var(--border); z-index: 0;
}
.cycle-node {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  position: relative; z-index: 1; flex: 1;
}
.cn-dot {
  width: 9px; height: 9px; border-radius: 50%;
  background: var(--bg-card); border: 1.5px solid var(--border-strong);
}
.cn-lbl { font-size: 10px; color: var(--text-subtle); white-space: nowrap; font-weight: 500; }
.cycle-node.active .cn-dot {
  width: 13px; height: 13px; background: var(--accent);
  border-color: var(--accent); box-shadow: 0 0 11px var(--accent);
}
.cycle-node.active .cn-lbl { color: var(--accent); font-weight: 800; font-size: 11.5px; }
.cycle-node.passed .cn-dot { background: var(--accent-dim); border-color: var(--accent-dim); }

/* ────────────────────────────────────────────────────────────────────────
   RRG 4-quadrant
   ──────────────────────────────────────────────────────────────────────── */
.rrg-grid {
  display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr;
  gap: 6px; margin-top: 4px;
}
.rrg-cell {
  border: 1px solid var(--border); border-radius: 5px;
  min-height: 52px; padding: 8px 6px; text-align: center;
  display: flex; flex-direction: column; justify-content: center; gap: 2px;
  color: var(--text-muted); font-weight: 600; font-size: 13px;
}
.rrg-cell .qd-sub { font-size: 8.5px; color: var(--text-subtle);
  text-transform: uppercase; letter-spacing: 0.08em; }
.rrg-cell .qd-op { font-size: 10px; font-weight: 700; margin-top: 2px; }
.rrg-axis { font-size: 9px; color: var(--text-subtle); text-align: center;
  text-transform: uppercase; letter-spacing: 0.1em; margin-top: 5px; }
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


_KIND_COLOR = {
    "success": "var(--success)", "danger": "var(--danger)",
    "warning": "var(--warning)", "accent": "var(--accent)",
    "muted": "var(--text-muted)",
}


def option_track(options: list[str], active: str, *,
                 kind_map: dict[str, str] | None = None,
                 default_kind: str = "accent",
                 vertical: bool = True) -> str:
    """Render every option in `options`, highlighting the `active` one and
    dimming the rest. `kind_map` colors each option (success|warning|danger|
    accent|muted); the active chip uses its kind color, others are muted.

    Use vertical=True for a stacked list (e.g. cycle phases), False for a row
    (e.g. risk lights).
    """
    kind_map = kind_map or {}
    chips: list[str] = []
    for opt in options:
        is_active = (opt == active)
        color = _KIND_COLOR.get(kind_map.get(opt, default_kind), "var(--accent)")
        if is_active:
            dot = (f'<span style="display:inline-block;width:7px;height:7px;'
                   f'border-radius:50%;background:{color};margin-right:9px;'
                   f'box-shadow:0 0 8px {color}"></span>')
            bg = f'color-mix(in srgb, {color} 13%, transparent)'
            bd = f'color-mix(in srgb, {color} 45%, transparent)'
            chips.append(
                f'<div style="display:flex;align-items:center;padding:6px 11px;'
                f'border-radius:5px;background:{bg};'
                f'border:1px solid {bd};border-left:3px solid {color};'
                f'margin:3px 0">'
                f'{dot}<span style="color:{color};font-size:14.5px;'
                f'font-weight:800;letter-spacing:0.02em">{opt}</span></div>'
            )
        else:
            chips.append(
                f'<div style="display:flex;align-items:center;padding:3px 9px;'
                f'margin:2px 0">'
                f'<span style="display:inline-block;width:6px;height:6px;'
                f'border-radius:50%;background:transparent;'
                f'border:1px solid var(--border);margin-right:7px"></span>'
                f'<span style="color:var(--text-muted);font-size:12px;'
                f'font-weight:500">{opt}</span></div>'
            )
    if vertical:
        return f'<div style="margin-top:2px">{"".join(chips)}</div>'
    return f'<div style="display:flex;gap:7px;margin-top:4px;flex-wrap:wrap">{"".join(chips)}</div>'


def progress_row(name: str, value: float, *, sub: str | None = None,
                  total: float = 100.0, kind: str = "accent") -> str:
    """Horizontal progress bar with label + value. `kind` ∈ accent|success|warning|danger."""
    pct = max(0.0, min(100.0, value / total * 100))
    sub_html = (f'<span class="pl-value">{value:.0f}/100 '
                f'<span style="color:var(--text-subtle);font-weight:500"> · {sub}</span></span>'
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


# Concept → emoji icon. First keyword hit wins; theme is the fallback.
_ICON_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("煤炭", "焦炭"), "⛏️"),
    (("石油", "油气", "油服", "天然气", "石化"), "🛢️"),
    (("光伏", "HJT", "BC电池"), "☀️"),
    (("风电",), "🌬️"),
    (("储能", "电池", "锂", "固态"), "🔋"),
    (("稀土", "永磁"), "🧲"),
    (("黄金", "贵金属", "珠宝"), "🥇"),
    (("钢", "工业金属", "有色", "铜"), "🏗️"),
    (("化工", "化学", "材料", "PEEK"), "⚗️"),
    (("机器人", "具身", "宇树"), "🤖"),
    (("减速器", "工程机械"), "⚙️"),
    (("光模块", "CPO", "光通信", "光芯片", "光电", "液冷", "铜缆"), "💡"),
    (("存储", "HBM", "长鑫"), "💾"),
    (("芯片", "半导体", "晶圆", "光刻", "封装", "EDA", "GPU", "ASIC", "MCU", "模拟"), "🔌"),
    (("AI", "智能体", "多模态", "算力", "英伟达", "AIGC", "AIPC"), "🧠"),
    (("卫星", "航天", "导航", "互联网"), "🛰️"),
    (("军工",), "🛡️"),
    (("低空", "无人机"), "🚁"),
    (("核聚变", "核电", "可控核"), "☢️"),
    (("量子",), "⚛️"),
    (("创新药", "仿制药", "疫苗", "CXO", "医疗", "器械", "减肥药"), "💊"),
    (("医美",), "💄"),
    (("宠物",), "🐾"),
    (("酒", "白酒"), "🍶"),
    (("食品", "饮料", "预制菜"), "🍱"),
    (("游戏", "短剧"), "🎮"),
    (("影视", "院线"), "🎬"),
    (("汽车", "华为汽车", "车路云"), "🚗"),
    (("数据", "数字", "信创", "元宇宙", "云计算"), "💻"),
    (("消费电子", "手机", "谷子", "零售", "婴童"), "🛍️"),
    (("航运", "港口", "船"), "🚢"),
    (("旅游",), "✈️"),
    (("猪", "养殖", "种植", "饲料", "农"), "🌾"),
]

_ICON_THEME: dict[str, str] = {
    "光通信/CPO": "💡", "存储": "💾", "机器人": "🤖", "半导体": "🔌",
    "AI算力": "🧠", "新能源": "🔋", "军工航天": "🛰️", "医药消费": "💊",
    "数字经济": "💻", "资源": "⛏️", "其他主线": "✨",
}


def concept_icon(concept: str | None, theme: str | None = None) -> str:
    """Small emoji icon for a concept/sector (keyword match, theme fallback)."""
    name = concept or ""
    for keys, icon in _ICON_KEYWORDS:
        if any(k in name for k in keys):
            return icon
    if theme and theme in _ICON_THEME:
        return _ICON_THEME[theme]
    return "▪"


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
        f'<div>'
        f'<div class="name">einvest</div>'
        f'<div class="tag">Terminal · v0.1</div>'
        f'</div>'
        f'</div>'
    )
