"""einvest 盘后 Web Dashboard (Streamlit)

Run with:
    streamlit run C:/projects/einvest/app/app.py

Sections:
  Top KPI       — 流动性 / breadth / 涨跌停 / MST_50 / CCI 简报
  CCI           — 4 主指数 + 偏多/超买/超卖分类
  板块热力图       — 颜色编码热力图（横向：概念，纵向：theme 分组）
  Top-K 迁移     — N 日涨幅 Top-K，新晋/连续/回归/掉出 标签
  板块周期详情      — SC30/SC3/SC60/heat/ret_5d/ret_20d/strength/phase
  热度历史        — 多选概念 + RSI+EMA(5) 时序
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow `from einvest...` regardless of where Streamlit was launched
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from einvest.config import STOCK_DIR
from einvest.cycle import cycle_detail_latest
from einvest.heatmap import band, heatmap_latest, heatmap_history
from einvest.indicators import (
    cci,
    classify_cci,
    limit_count,
    liquidity_band,
    liquidity_score,
    mst,
    up_down_count,
)
from einvest.io import (
    latest_concept_date,
    load_close_panel,
    load_full_a,
    load_index,
    stock_name,
    universe,
)
from einvest.crowding import crowding_latest_per_concept, market_crowding_state
from einvest.market_state import market_state_snapshot
from einvest.rrg import rrg_latest_per_concept, stock_rrg
from einvest.rankings import (
    latest_topk_migration,
    n_day_return,
    sector_close_panel,
)
from einvest.sectors import HOT_CONCEPTS, MAIN_INDICES
from einvest.tags import generate_stock_tags

from style import (
    GLOBAL_CSS, brand_bar, kpi_card, pill,
    section_header, sidebar_brand,
)


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="einvest Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Cached loaders
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="加载个股 close panel ...")
def _close_panel() -> pd.DataFrame:
    return load_close_panel(universe())


@st.cache_data(show_spinner="加载 universe ...")
def _universe() -> list[str]:
    return universe()


@st.cache_data(show_spinner="加载板块 close panel ...")
def _sector_panel() -> pd.DataFrame:
    return sector_close_panel()


@st.cache_data(show_spinner="计算板块热力图 ...")
def _heatmap_latest() -> pd.DataFrame:
    return heatmap_latest()


@st.cache_data(show_spinner="计算板块周期详情 ...")
def _cycle_detail() -> pd.DataFrame:
    return cycle_detail_latest()


@st.cache_data(show_spinner="加载万得全A ...")
def _full_a() -> pd.DataFrame:
    return load_full_a()


@st.cache_data(show_spinner="加载主指数 ...")
def _index(code: str) -> pd.DataFrame:
    return load_index(code)


@st.cache_data(show_spinner="计算涨跌停 ...")
def _limit_count(codes: tuple[str, ...]) -> pd.DataFrame:
    return limit_count(STOCK_DIR, list(codes))


@st.cache_data(show_spinner="计算热度时序 ...")
def _heatmap_history() -> pd.DataFrame:
    return heatmap_history()


@st.cache_data(show_spinner="加载 universe amount panel ...")
def _amount_panel() -> pd.DataFrame:
    """Universe-wide total_turnover panel — shared by crowding + capacity tags."""
    from einvest.io import load_panel
    return load_panel(_universe(), field="total_turnover").sort_index()


@st.cache_data(show_spinner="计算市场状态 ...")
def _market_state():
    return market_state_snapshot(
        full_a=_full_a(),
        close_panel=_close_panel(),
        cycle_detail=_cycle_detail(),
    )


@st.cache_data(show_spinner="计算容量抱团 ...")
def _crowding() -> pd.DataFrame:
    full_a = _full_a()
    market_amt = full_a.set_index("date")["amt"] if not full_a.empty else None
    return crowding_latest_per_concept(
        universe_amt_panel=_amount_panel(),
        market_amt=market_amt,
        sector_panel=_sector_panel(),
    )


@st.cache_data(show_spinner="计算 RRG 轮动 ...")
def _rrg() -> pd.DataFrame:
    return rrg_latest_per_concept()


@st.cache_data(show_spinner="构建标签引擎 ...")
def _tag_theme_snapshot() -> dict[str, dict]:
    """Pre-compute theme snapshot for tag engine (reuses cached cycle + panel)."""
    cyc = _cycle_detail()
    panel = _sector_panel()

    cyc_map: dict[str, dict] = {}
    for _, row in cyc.iterrows():
        cyc_map[row["concept"]] = {
            "sc30": row.get("SC30", float("nan")),
            "sc3": row.get("SC3", float("nan")),
            "heat": row.get("heat", float("nan")),
            "phase": row.get("phase", "n/a"),
            "strength": row.get("strength", "n/a"),
            "ret_5d": row.get("ret_5d", float("nan")),
            "ret_20d": row.get("ret_20d", float("nan")),
            "theme": row.get("theme", ""),
        }

    top7 = set()
    top7_rank: dict[str, int] = {}
    if not panel.empty and len(panel) > 5:
        rets = n_day_return(panel, 5)
        last = rets.iloc[-1].dropna().sort_values(ascending=False).head(7)
        for i, concept in enumerate(last.index, start=1):
            top7.add(concept)
            top7_rank[concept] = i

    for concept, info in cyc_map.items():
        info["in_top7"] = concept in top7
        info["top7_rank"] = top7_rank.get(concept, None)
    return cyc_map


# ---------------------------------------------------------------------------
# Sidebar — brand + universe stats + actions
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(sidebar_brand(), unsafe_allow_html=True)
    st.markdown("##### Universe")
    u = _universe()
    cd = latest_concept_date()
    st.markdown(
        kpi_card("覆盖股票数", f"{len(u):,}", value_size="sm",
                 delta=f"Wind 概念缓存 · {cd or 'n/a'}") +
        kpi_card("概念数", str(sum(len(v) for v in HOT_CONCEPTS.values())),
                 value_size="sm", delta=f"{len(HOT_CONCEPTS)} 个主题"),
        unsafe_allow_html=True,
    )
    st.write("")  # spacer
    if st.button("🔄 清缓存重算", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"数据根：`{STOCK_DIR.parent.parent}`")


# ---------------------------------------------------------------------------
# Brand header (replaces old st.title)
# ---------------------------------------------------------------------------

full_a = _full_a()
last_date_str = (full_a["date"].iloc[-1].date().isoformat()
                 if not full_a.empty else "—")

# Probe market state early so the header pill can reflect today's state
_PHASE_KIND = {
    "高潮": "danger",
    "抱团": "warning",
    "主流轮动": "accent",
    "下降趋势": "accent",
    "酝酿": "muted",
    "缩容": "warning",
    "瓦解": "danger",
    "中性": "muted",
    "n/a": "muted",
}
snap = _market_state()
cycle_label = snap.cycle_phase if snap is not None else None
cycle_kind = _PHASE_KIND.get(cycle_label, "muted") if cycle_label else "muted"

st.markdown(
    brand_bar(
        trade_date=last_date_str,
        n_stocks=len(u),
        n_themes=len(HOT_CONCEPTS),
        state=cycle_label,
        state_kind=cycle_kind,
    ),
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Hero panel — market state composite
# ---------------------------------------------------------------------------

if snap is not None:
    st.markdown(
        section_header("周期阶段", "Market cycle phase · SC30 + Breadth + MST + Liquidity"),
        unsafe_allow_html=True,
    )

    ph1, ph2 = st.columns([1, 1])
    ph1.markdown(
        kpi_card(
            "当前阶段",
            pill(snap.cycle_phase, kind=_PHASE_KIND.get(snap.cycle_phase, "muted"), size="lg"),
            delta=(
                f"市场 SC30 = {snap.breadth.get('market_sc30') or '—'}"
                f"  ·  breadth = {snap.breadth['breadth_ratio']:.2f}"
                f"  ·  MST5 = {snap.position_flex['mst_5']:.1f}"
            ),
        ),
        unsafe_allow_html=True,
    )
    ph2.markdown(
        kpi_card(
            "流动性",
            snap.position_flex["liquidity_band"],
            delta=f"评分 {snap.position_flex['liquidity_score']}  ·  CCI84 = {snap.position_flex['cci84'] or '—'}",
        ),
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Top KPI strip — quick market vitals
# ---------------------------------------------------------------------------

close_panel = _close_panel()
codes_for_lim = tuple(_universe())
liq_score = float(liquidity_score(full_a.set_index("date")["amt"], 252).iloc[-1])
liq_amt_yi = float(full_a["amt"].iloc[-1]) / 1e8
mst_df = mst(close_panel, windows=(5, 13, 50))
mst_5 = float(mst_df["MST_5"].iloc[-1])
mst_50 = float(mst_df["MST_50"].iloc[-1])
udc = up_down_count(close_panel).iloc[-1]
lc = _limit_count(codes_for_lim)
lim_up = int(lc["limit_up_count"].iloc[-1]) if not lc.empty else 0
lim_dn = int(lc["limit_down_count"].iloc[-1]) if not lc.empty else 0
br = float(udc["breadth_ratio"])
cb = _index("399006.XSHE")
cb_cci84 = float(cci(cb, 84).iloc[-1]) if not cb.empty else float("nan")

st.markdown(
    section_header("市场快照", "Top-of-book vitals"),
    unsafe_allow_html=True,
)
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.markdown(
    kpi_card("流动性 (亿)", f"{liq_amt_yi:,.0f}",
             delta=f"评分 {liq_score:.1f} · {liquidity_band(liq_score)}"),
    unsafe_allow_html=True,
)
breadth_kind = "up" if br >= 1.0 else "down"
k2.markdown(
    kpi_card("Breadth", f"{br:.2f}",
             delta=f"↑{int(udc['up_count'])}  ↓{int(udc['down_count'])}",
             delta_kind=breadth_kind),
    unsafe_allow_html=True,
)
k3.markdown(
    kpi_card("涨停 / 跌停", f"{lim_up} / {lim_dn}",
             delta=f"差额 {lim_up - lim_dn:+d}",
             delta_kind="up" if lim_up > lim_dn else "down"),
    unsafe_allow_html=True,
)
k4.markdown(
    kpi_card("MST-5  短线", f"{mst_5:.1f}",
             delta="% 站上 5 日均线"),
    unsafe_allow_html=True,
)
k5.markdown(
    kpi_card("MST-50  趋势", f"{mst_50:.1f}",
             delta="% 站上 50 日均线"),
    unsafe_allow_html=True,
)
cci_state = classify_cci(cb_cci84)
cci_kind = "down" if cci_state == "超买" else ("up" if cci_state == "超卖" else "muted")
k6.markdown(
    kpi_card("创业板 CCI84", f"{cb_cci84:.0f}",
             delta=cci_state, delta_kind=cci_kind),
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tabs = st.tabs([
    "📍 市场状态",
    "📈 CCI",
    "🔥 板块热力图",
    "🏆 Top-K 排名迁移",
    "💧 容量抱团",
    "🌐 RRG 轮动",
    "🌗 板块周期详情",
    "📉 热度历史",
    "🏷️ 个股标签",
])

# -------- Tab 0: Market state detail ---------
with tabs[0]:
    if snap is None:
        st.warning("无法计算市场状态：万得全A 数据缺失。")
    else:
        msc30 = snap.breadth.get("market_sc30")
        msc3 = snap.breadth.get("market_sc3")

        # Market SC30/SC3 KPI row
        ms1, ms2, ms3, ms4 = st.columns(4)
        ms1.markdown(
            kpi_card("市场 SC30",
                     f"{msc30}" if msc30 is not None else "—",
                     delta="万得全A · RSV₃₀ · 中期强弱",
                     accent=True),
            unsafe_allow_html=True,
        )
        ms2.markdown(
            kpi_card("市场 SC3",
                     f"{msc3}" if msc3 is not None else "—",
                     delta="万得全A · RSV₃ · 短期强弱"),
            unsafe_allow_html=True,
        )
        ms3.markdown(
            kpi_card("breadth_ratio",
                     f"{snap.breadth['breadth_ratio']:.2f}",
                     delta=f"↑{snap.breadth['up_count']}  ↓{snap.breadth['down_count']}",
                     delta_kind="up" if snap.breadth['breadth_ratio'] >= 1.0 else "down"),
            unsafe_allow_html=True,
        )
        ms4.markdown(
            kpi_card("热点 SC30 (max)",
                     f"{snap.breadth.get('top_sc30') or '—'}",
                     delta="最强概念 SC30"),
            unsafe_allow_html=True,
        )

        st.markdown(
            section_header("规则与口径", "Methodology"),
            unsafe_allow_html=True,
        )
        st.markdown(
            """
- **市场 SC30** = 万得全A 收盘的 30 日 RSV，对标原始框架的 SC30 中期（如原框架 46.9）
- **周期阶段**（市场级，基于 SC30 万得全A）：
  - 高潮：SC30 ≥ 80 且强势板块 ≥ 20% 且 breadth_ratio > 1.2
  - 抱团：SC30 ≥ 70 且强势板块 ≥ 25%
  - 主流轮动：SC30 ≥ 55 且强势板块 ≥ 15%
  - 下降趋势：SC30 < 55 且 breadth_ratio < 1.0（对标原框架 B2_EXIT / 下降趋势）
  - 缩容：流动性匮乏 且 MST5 < 40
  - 瓦解：SC30 < 30 且 breadth_ratio < 0.5
  - 酝酿：强势板块 < 10% 且 SC30 < 50

> ⚠️ 市场温度 / 仓位三分法（§10）口径尚在对齐中，暂不显示。
            """
        )

# -------- Tab 1: CCI ---------
with tabs[1]:
    st.subheader("CCI — 主指数顶底")
    cci_rows = []
    for name, code in MAIN_INDICES.items():
        df = _index(code)
        if df.empty:
            continue
        c14 = cci(df, 14)
        c84 = cci(df, 84)
        cci_rows.append({
            "name": name,
            "code": code,
            "close": round(float(df["close"].iloc[-1]), 2),
            "cci14": round(float(c14.iloc[-1]), 2),
            "状态14": classify_cci(c14.iloc[-1]),
            "cci84": round(float(c84.iloc[-1]), 2),
            "状态84": classify_cci(c84.iloc[-1]),
        })
    cci_df = pd.DataFrame(cci_rows)

    def _color_state(v: str) -> str:
        return {
            "超买": "background-color: #fde0e0; color: #c70000",
            "偏多": "background-color: #fff7e0; color: #b88500",
            "偏空": "background-color: #eaf2ff; color: #0050b3",
            "超卖": "background-color: #e0f0ff; color: #003a8c",
        }.get(v, "")

    sty = cci_df.style.applymap(_color_state, subset=["状态14", "状态84"]) \
        .format({"close": "{:.2f}", "cci14": "{:.2f}", "cci84": "{:.2f}"})
    st.dataframe(sty, width="stretch", hide_index=True)
    st.caption("CCI14 短期；CCI84 中长期。>100 超买，0~100 偏多，-100~0 偏空，<-100 超卖。")

# -------- Tab 2: Heatmap ---------
with tabs[2]:
    st.subheader("板块热力图 — RSI(14) 板块价 → EMA(5)")

    h = _heatmap_latest().copy()
    h = h.dropna(subset=["heat"])

    # Color-coded heatmap (one row per theme, one cell per concept)
    themes = list(HOT_CONCEPTS.keys())
    max_cols = max(len(v) for v in HOT_CONCEPTS.values())

    z = np.full((len(themes), max_cols), np.nan)
    text = np.full((len(themes), max_cols), "", dtype=object)
    hover = np.full((len(themes), max_cols), "", dtype=object)
    for i, theme in enumerate(themes):
        for j, concept in enumerate(HOT_CONCEPTS[theme]):
            row = h[h["concept"] == concept]
            if row.empty:
                continue
            r = row.iloc[0]
            z[i, j] = r["heat"]
            arrow = r["arrow"] if r["arrow"] != "n/a" else ""
            text[i, j] = f"{concept}<br>{r['heat']:.0f} {arrow}"
            hover[i, j] = (
                f"{concept}<br>heat={r['heat']:.1f}<br>"
                f"昨日={r['prev_heat']:.1f} Δ={r['delta']:+.2f}<br>"
                f"色带={r['band']}<br>n={r['n_stocks']}"
            )

    fig = go.Figure(go.Heatmap(
        z=z,
        text=text,
        texttemplate="%{text}",
        hoverinfo="text",
        hovertext=hover,
        x=[f"col{i+1}" for i in range(max_cols)],
        y=themes,
        colorscale=[
            [0.00, "#0f7d4a"],   # 深绿
            [0.35, "#52c47a"],   # 绿
            [0.45, "#a8e0b5"],   # 亮绿
            [0.50, "#fff3b0"],   # 黄
            [0.55, "#ffd9a0"],   # 浅红
            [0.65, "#ff9b6c"],   # 红
            [0.75, "#e8593b"],   # 深红
            [0.90, "#9b30b3"],   # 紫红
            [1.00, "#5e0066"],
        ],
        zmin=0, zmax=100,
        showscale=True,
        colorbar=dict(title="heat"),
    ))
    fig.update_layout(
        height=70 * len(themes) + 100,
        margin=dict(l=80, r=20, t=20, b=20),
        xaxis=dict(showticklabels=False, showgrid=False),
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, width="stretch")

    with st.expander("热力图全表（按 heat 降序）"):
        cols = ["theme", "concept", "heat", "delta", "arrow", "band", "n_stocks"]
        st.dataframe(h[cols].sort_values("heat", ascending=False),
                     width="stretch", hide_index=True)


# -------- Tab 3: Top-K migration ---------
with tabs[3]:
    st.subheader("板块 Top-K N日涨幅排名 + 迁移")

    col_a, col_b = st.columns([1, 4])
    n_days = col_a.selectbox("N 日窗口", [1, 3, 5, 10, 20], index=2, key="topk_n_days")
    k = col_a.selectbox("Top K", [3, 5, 7, 10], index=2, key="topk_k")

    sec_panel = _sector_panel()
    rets = n_day_return(sec_panel, n_days)
    last = rets.iloc[-1].dropna().sort_values(ascending=False).head(k)

    top_df = pd.DataFrame({
        "rank": range(1, len(last) + 1),
        "concept": last.index,
        f"{n_days}日涨幅(%)": last.values.round(2),
    })

    col_b.markdown(f"#### 今日 Top {k} (按 {n_days} 日涨幅)")
    col_b.dataframe(top_df, width="stretch", hide_index=True)

    st.markdown("#### 迁移（今日 ∪ 昨日 Top-K）")
    mig = latest_topk_migration(rets, k=k)
    if not mig.empty:
        tag_color = {
            "连续": "background-color: #f5f5f5; color: #595959",
            "新晋": "background-color: #d9f7be; color: #237804",
            "回归": "background-color: #e6f4ff; color: #003a8c",
            "掉出": "background-color: #fff1f0; color: #cf1322",
        }
        sty = mig.style.applymap(
            lambda v: tag_color.get(v, ""), subset=["tag"]
        ).format({"ret_pct_today": "{:.2f}"})
        st.dataframe(sty, width="stretch", hide_index=True)


# -------- Tab 4: Crowding (容量抱团) ---------
with tabs[4]:
    st.markdown(
        section_header("容量抱团", "Capital concentration in leading themes"),
        unsafe_allow_html=True,
    )

    cr = _crowding()
    if cr.empty:
        st.info("无可用容量抱团数据。")
    else:
        mc = market_crowding_state(cr)
        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(
            kpi_card("Top 主题", f"{mc.get('top_theme', '—')}",
                     delta=f"占全市 {mc.get('top_theme_share_pct', 0):.2f}%",
                     value_size="sm", accent=True),
            unsafe_allow_html=True,
        )
        m2.markdown(
            kpi_card("Top2 浓度", f"{mc.get('top2_concentration_pct', 0):.2f}%",
                     delta="Top1 + Top2 主题占全市"),
            unsafe_allow_html=True,
        )
        decay_val = mc.get("top_theme_decay_pct")
        m3.markdown(
            kpi_card("Top 主题衰减",
                     f"{decay_val:.1f}%" if decay_val is not None else "—",
                     delta="从 60 日峰值的回落幅度"),
            unsafe_allow_html=True,
        )
        abs_c = mc.get("abs_crowding", False)
        abs_pill = (pill("触发", kind="danger", size="lg") if abs_c
                    else pill("未触发", kind="success", size="lg"))
        m4.markdown(
            kpi_card("绝对抱团", abs_pill,
                     delta=f"阈值 {mc.get('abs_share_threshold_pct', 8):.0f}%"),
            unsafe_allow_html=True,
        )

        st.markdown(
            section_header("概念级容量明细", "Sorted by market share, descending"),
            unsafe_allow_html=True,
        )

        # Filters
        col_a, col_b = st.columns([1, 4])
        only_top7 = col_a.checkbox("只看 in Top7", value=False, key="crowding_only_top7")
        min_share = col_a.number_input("最小 share (%)", value=0.5, step=0.5, key="crowding_min_share")

        view = cr.copy()
        if only_top7:
            view = view[view["days_in_top7"] > 0]
        view = view[view["share_pct"] >= min_share]

        show_cols = [
            "theme", "concept", "top_n_amount_yi", "share_pct",
            "strength_pct", "decay_pct", "days_in_top7",
        ]
        view = view[show_cols].rename(columns={
            "top_n_amount_yi": "top5成交额(亿)",
            "share_pct": "占全市(%)",
            "strength_pct": "60日分位(%)",
            "decay_pct": "衰减(%)",
            "days_in_top7": "Top7连续天",
        })
        sty = view.style \
            .background_gradient(subset=["占全市(%)"], cmap="Reds", vmin=0, vmax=8) \
            .background_gradient(subset=["60日分位(%)"], cmap="Reds", vmin=0, vmax=100) \
            .background_gradient(subset=["衰减(%)"], cmap="Blues", vmin=0, vmax=40) \
            .format({"top5成交额(亿)": "{:.0f}", "占全市(%)": "{:.2f}",
                     "60日分位(%)": "{:.0f}", "衰减(%)": "{:.1f}"})
        st.dataframe(sty, width="stretch", hide_index=True, height=520)

        st.caption(
            "**share_pct** = 主题 top5 成交额 / 全市场成交额 × 100。"
            "**60日分位** = share_pct 在过去 60 日的滚动百分位（接近 100 = 历史高位）。"
            "**衰减** = (60日峰值 − 当前 share) / 峰值 × 100。"
            "**Top7连续天** = 在 5 日涨幅 Top7 中连续在榜天数。"
        )


# -------- Tab 5: RRG rotation ---------
with tabs[5]:
    st.markdown(
        section_header("RRG 相对轮动", "Sector momentum vs CSI 300"),
        unsafe_allow_html=True,
    )

    rdf = _rrg()
    if rdf.empty:
        st.info("无可用 RRG 数据。")
    else:
        # Quadrant counts
        qc = rdf["quadrant"].value_counts()
        q1, q2, q3, q4 = st.columns(4)
        q1.markdown(kpi_card("领涨 Leading",  str(qc.get("领涨", 0)),
                             delta="RS+ · MOM+", accent=True), unsafe_allow_html=True)
        q2.markdown(kpi_card("转强 Improving", str(qc.get("转强", 0)),
                             delta="RS- · MOM+"), unsafe_allow_html=True)
        q3.markdown(kpi_card("转弱 Weakening", str(qc.get("转弱", 0)),
                             delta="RS+ · MOM-"), unsafe_allow_html=True)
        q4.markdown(kpi_card("落后 Lagging",   str(qc.get("落后", 0)),
                             delta="RS- · MOM-"), unsafe_allow_html=True)

        # Theme filter
        col_a, col_b = st.columns([1, 4])
        sel_theme = col_a.multiselect(
            "主题筛选",
            sorted(rdf["theme"].dropna().unique()),
            key="rrg_theme_filter",
        )
        show_trail = col_a.checkbox("显示轨迹", value=True, key="rrg_show_trail")
        view = rdf if not sel_theme else rdf[rdf["theme"].isin(sel_theme)]
        view = view.dropna(subset=["rs_ratio", "rs_momentum"])

        # Scatter plot
        fig = go.Figure()

        # Quadrant background shading
        fig.add_shape(type="rect", x0=0, y0=0, x1=5, y1=5,
                      fillcolor="rgba(82, 196, 122, 0.10)", line_width=0)  # 领涨
        fig.add_shape(type="rect", x0=-5, y0=0, x1=0, y1=5,
                      fillcolor="rgba(64, 169, 255, 0.10)", line_width=0)  # 转强
        fig.add_shape(type="rect", x0=0, y0=-5, x1=5, y1=0,
                      fillcolor="rgba(255, 215, 100, 0.10)", line_width=0)  # 转弱
        fig.add_shape(type="rect", x0=-5, y0=-5, x1=0, y1=0,
                      fillcolor="rgba(255, 130, 130, 0.10)", line_width=0)  # 落后

        fig.add_hline(y=0, line_dash="dot", line_color="#999")
        fig.add_vline(x=0, line_dash="dot", line_color="#999")

        # Quadrant labels (corner annotations)
        fig.add_annotation(x=3.5, y=3.5, text="<b>领涨 Leading</b>",
                            showarrow=False, font=dict(color="#237804", size=14))
        fig.add_annotation(x=-3.5, y=3.5, text="<b>转强 Improving</b>",
                            showarrow=False, font=dict(color="#003a8c", size=14))
        fig.add_annotation(x=3.5, y=-3.5, text="<b>转弱 Weakening</b>",
                            showarrow=False, font=dict(color="#874d00", size=14))
        fig.add_annotation(x=-3.5, y=-3.5, text="<b>落后 Lagging</b>",
                            showarrow=False, font=dict(color="#cf1322", size=14))

        # Plot trails first (so points are on top)
        if show_trail:
            for _, row in view.iterrows():
                tr = [v for v in row["trail_rs"] if v is not None]
                tm = [v for v in row["trail_mom"] if v is not None]
                if len(tr) < 2:
                    continue
                fig.add_trace(go.Scatter(
                    x=tr, y=tm, mode="lines",
                    line=dict(color="rgba(150,150,150,0.35)", width=1),
                    hoverinfo="skip", showlegend=False,
                ))

        # Plot current positions, color by quadrant
        qcolor = {"领涨": "#52c47a", "转强": "#40a9ff",
                  "转弱": "#fa8c16", "落后": "#cf1322"}
        for q, color in qcolor.items():
            sub = view[view["quadrant"] == q]
            if sub.empty:
                continue
            fig.add_trace(go.Scatter(
                x=sub["rs_ratio"], y=sub["rs_momentum"],
                mode="markers+text",
                marker=dict(color=color, size=11, line=dict(color="white", width=1)),
                text=sub["concept"],
                textposition="top center",
                textfont=dict(size=10),
                name=q,
                hovertemplate="<b>%{text}</b><br>RS=%{x:.2f} MOM=%{y:.2f}<extra></extra>",
            ))

        fig.update_layout(
            height=620,
            xaxis=dict(title="RS-Ratio (相对强度)", range=[-5, 5], zeroline=False),
            yaxis=dict(title="RS-Momentum (强度变化率)", range=[-5, 5], zeroline=False),
            margin=dict(l=40, r=20, t=30, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.5, xanchor="center"),
        )
        st.plotly_chart(fig, width="stretch")

        with st.expander("RRG 全表 (按象限分组)"):
            show = view[["theme", "concept", "rs_ratio", "rs_momentum", "quadrant"]] \
                    .sort_values(["quadrant", "rs_ratio"], ascending=[True, False])
            st.dataframe(show, width="stretch", hide_index=True)

        st.caption(
            "**RS-Ratio** = (板块/沪深300) 价格比的 60 日滚动 Z-score。"
            "**RS-Momentum** = RS-Ratio 5 日变化值的 60 日滚动 Z-score。"
            "**轨迹** 显示最近 5 个交易日的位置变化（灰线 = 较早，端点 = 今天）。"
            "通常路径：转强 → 领涨 → 转弱 → 落后 → 转强。"
        )


# -------- Tab 6: Cycle detail ---------
with tabs[6]:
    st.subheader("板块周期详情 — SC30/SC3/SC60 + heat + 5/20日涨幅")

    cyc = _cycle_detail()

    col_a, col_b, col_c = st.columns(3)
    sel_theme = col_a.multiselect(
        "主题筛选",
        sorted(cyc["theme"].dropna().unique()),
        key="cycle_theme_filter",
    )
    sel_strength = col_b.multiselect(
        "强度",
        ["偏热", "强势", "中性", "冰点", "n/a"],
        key="cycle_strength_filter",
    )
    sel_phase = col_c.multiselect(
        "周期阶段",
        ["高潮", "高位回调", "强势", "抱团", "酝酿反弹", "酝酿", "底部反弹", "冰点", "n/a"],
        key="cycle_phase_filter",
    )

    view = cyc.copy()
    if sel_theme:
        view = view[view["theme"].isin(sel_theme)]
    if sel_strength:
        view = view[view["strength"].isin(sel_strength)]
    if sel_phase:
        view = view[view["phase"].isin(sel_phase)]

    show_cols = ["theme", "concept", "n_stocks", "SC30", "SC3", "SC60",
                 "heat", "ret_5d", "ret_20d", "strength", "phase"]

    strength_color = {
        "偏热":  "background-color: #ffd9a0; color: #cf1322",
        "强势":  "background-color: #fff3b0; color: #ad6800",
        "中性":  "background-color: #f5f5f5; color: #595959",
        "冰点":  "background-color: #d6e7ff; color: #003a8c",
    }
    phase_color = {
        "高潮":   "background-color: #ffb3a7; color: #780600",
        "高位回调": "background-color: #ffe1a8; color: #874d00",
        "强势":   "background-color: #fff3b0; color: #ad6800",
        "抱团":   "background-color: #e8f7d6; color: #237804",
        "酝酿反弹": "background-color: #d6e7ff; color: #003a8c",
        "酝酿":   "background-color: #f5f5f5; color: #595959",
        "底部反弹": "background-color: #cdeefd; color: #003a8c",
        "冰点":   "background-color: #d6e7ff; color: #003a8c",
    }
    sty = view[show_cols].style \
        .applymap(lambda v: strength_color.get(v, ""), subset=["strength"]) \
        .applymap(lambda v: phase_color.get(v, ""), subset=["phase"]) \
        .background_gradient(subset=["SC30", "SC3", "SC60", "heat"],
                              cmap="RdYlGn_r", vmin=0, vmax=100) \
        .background_gradient(subset=["ret_5d", "ret_20d"], cmap="RdYlGn", vmin=-15, vmax=15) \
        .format({"SC30": "{:.1f}", "SC3": "{:.1f}", "SC60": "{:.1f}",
                 "heat": "{:.1f}", "ret_5d": "{:.2f}", "ret_20d": "{:.2f}"})
    st.dataframe(sty, width="stretch", hide_index=True, height=600)

    # Pie / distribution
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**强度分布**")
        sd = view["strength"].value_counts()
        st.bar_chart(sd)
    with col2:
        st.markdown("**周期阶段分布**")
        pd_ = view["phase"].value_counts()
        st.bar_chart(pd_)


# -------- Tab 7: Heat history ---------
with tabs[7]:
    st.subheader("板块热度时序 — RSI(14) + EMA(5)")

    hh = _heatmap_history()
    if hh.empty:
        st.info("无可用历史。")
    else:
        default_pick = (
            _heatmap_latest().dropna(subset=["heat"]).head(6)["concept"].tolist()
        )
        picked = st.multiselect(
            "选择概念",
            options=list(hh.columns),
            default=default_pick,
            key="heat_history_concepts",
        )
        lookback = st.slider("回看天数", 30, 750, 250, step=30, key="heat_history_lookback")

        if picked:
            view = hh[picked].tail(lookback).copy()
            fig = px.line(
                view, x=view.index, y=view.columns,
                labels={"value": "heat", "variable": "concept"},
            )
            fig.add_hline(y=85, line_dash="dot", line_color="purple",
                          annotation_text="紫红 (>=85)")
            fig.add_hline(y=75, line_dash="dot", line_color="red",
                          annotation_text="深红 (75-85)")
            fig.add_hline(y=50, line_dash="dot", line_color="grey")
            fig.add_hline(y=35, line_dash="dot", line_color="green",
                          annotation_text="绿 (<35)")
            fig.update_layout(height=520, hovermode="x unified",
                              margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, width="stretch")


# -------- Tab 8: Stock tags ---------
with tabs[8]:
    st.subheader("个股标签 — 量化交易状态")

    col_input, _ = st.columns([1, 3])
    stock_input = col_input.text_input(
        "输入股票代码",
        value="000001.XSHE",
        placeholder="例如: 000001.XSHE 或 000001.SZ",
    )

    if stock_input:
        snapshot = _tag_theme_snapshot()
        with st.spinner("计算标签..."):
            result = generate_stock_tags(stock_input, theme_snapshot=snapshot)

        if not result["features"]:
            st.error(f"无法获取 {stock_input} 的数据（可能不在当前 universe 中或数据不足）")
        else:
            feats = result["features"]
            themes = result["themes"]
            tags = result["tags"]
            evidence = result["tag_evidence"]
            stock_display_name = stock_name(result["code"])

            display_title = result["code"]
            if stock_display_name:
                display_title = f"{stock_display_name} · {result['code']}"
            st.markdown(f"### {display_title}")

            # --- Top row: basic info ---
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("收盘价", f"{feats['close']:.2f}")
            c2.metric("1日涨幅", f"{feats['ret_1d']:.2f}%")
            c3.metric("5日涨幅", f"{feats['ret_5d']:.2f}%")
            c4.metric("20日涨幅", f"{feats['ret_20d']:.2f}%")
            c5.metric("成交额分位", f"{feats['amount_pct_60d']:.0f}%")
            c6.metric("20日回撤", f"{feats['drawdown_from_high']:.1f}%")

            # --- Tag badges ---
            st.markdown("### 交易标签")
            if not tags:
                st.info("暂无匹配标签")
            else:
                tag_color = {
                    # 现有
                    "主线核心":       ("#237804", "#d9f7be"),
                    "容量焦点":       ("#874d00", "#fff3b0"),
                    "强趋势":         ("#ad6800", "#fff3b0"),
                    "高拥挤":         ("#cf1322", "#fff1f0"),
                    "回调观察":       ("#003a8c", "#e6f4ff"),
                    "超跌反弹":       ("#003a8c", "#d6e7ff"),
                    "右侧确认":       ("#237804", "#e8f7d6"),
                    "放量突破":       ("#ad6800", "#ffe1a8"),
                    "涨停基因":       ("#cf1322", "#fde0e0"),
                    "缩量回调":       ("#595959", "#f5f5f5"),
                    # §10.5 趋势卡位
                    "趋势卡位买点":   ("#874d00", "#ffe1a8"),
                    "趋势卡位精选":   ("#780600", "#ffb3a7"),
                    # §10.6 5层抄底
                    "抄底·绝底(95)": ("#780600", "#ffb3a7"),
                    "抄底·超高(87)": ("#cf1322", "#fde0e0"),
                    "抄底·高(81)":   ("#ad6800", "#fff3b0"),
                    "抄底·中高(68)": ("#003a8c", "#e6f4ff"),
                    "抄底·中(60)":   ("#595959", "#f5f5f5"),
                    # §10.7 情绪龙头
                    "涨停":           ("#cf1322", "#fde0e0"),
                    "夺命板":         ("#780600", "#ffb3a7"),
                    "攻击资金共振":   ("#ad6800", "#fff3b0"),
                }
                badge_html = ""
                for tag in tags:
                    # 连板·N板 / 连板·2板 etc. all share color
                    color_key = "涨停" if tag.startswith("连板·") else tag
                    fg, bg = tag_color.get(color_key, ("#595959", "#f5f5f5"))
                    badge_html += (
                        f'<span style="background-color:{bg};color:{fg};'
                        f'padding:4px 12px;border-radius:12px;margin:4px;'
                        f'font-weight:600;font-size:14px;display:inline-block">'
                        f'{tag}</span>'
                    )
                st.markdown(badge_html, unsafe_allow_html=True)

                with st.expander("标签依据"):
                    for tag in tags:
                        st.markdown(f"**{tag}**：{evidence.get(tag, '')}")

            # --- MA status + RRG quadrant ---
            st.markdown("### 均线状态 + RRG 象限")
            ma_cols = st.columns(4)
            ma_labels = [("MA5",  "above_ma5"), ("MA13", "above_ma13"), ("MA50", "above_ma50")]
            for col, (name, key) in zip(ma_cols[:3], ma_labels):
                on = feats[key]
                col.metric(name, "站上 ✅" if on else "下方 ❌")

            # RRG (vs 沪深300)
            from einvest.io import load_stock as _load_stk
            stk_df = _load_stk(result["code"])
            if not stk_df.empty:
                close_s = stk_df.set_index("date")["close"].sort_index()
                rrg_info = stock_rrg(close_s)
                q_icon = {"领涨": "🟢", "转强": "🔵", "转弱": "🟡", "落后": "🔴", "n/a": "⚪"}
                ma_cols[3].metric(
                    "RRG 象限",
                    f"{q_icon.get(rrg_info['quadrant'], '⚪')} {rrg_info['quadrant']}",
                    f"RS={rrg_info['rs_ratio']} MOM={rrg_info['rs_momentum']}"
                    if rrg_info["rs_ratio"] is not None else "n/a",
                )

            # --- Theme membership table ---
            st.markdown("### 所属主题状态")
            if themes:
                theme_rows = []
                for t in themes:
                    tr = t.get("top7_rank")
                    ar = t.get("amount_rank")
                    theme_rows.append({
                        "主题": t["theme"],
                        "概念": t["concept"],
                        "SC30": t.get("sc30", float("nan")),
                        "heat": t.get("heat", float("nan")),
                        "强度": t.get("strength", "n/a"),
                        "阶段": t.get("phase", "n/a"),
                        "Top7": "是" if t.get("in_top7") else "否",
                        "排名": int(tr) if tr is not None else "—",
                        "成交额排名": int(ar) if ar is not None else "—",
                    })
                tdf = pd.DataFrame(theme_rows)
                sty = tdf.style \
                    .background_gradient(subset=["SC30", "heat"], cmap="RdYlGn_r", vmin=0, vmax=100) \
                    .format({"SC30": "{:.1f}", "heat": "{:.1f}"})
                st.dataframe(sty, width="stretch", hide_index=True)
            else:
                st.info("该股票不在当前热门板块 universe 中")
