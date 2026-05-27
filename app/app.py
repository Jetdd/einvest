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
from einvest.risk_score import risk_score_snapshot, risk_light_from_stats
from einvest.rrg import rrg_rotation_table, stock_rrg
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


@st.cache_data(show_spinner="计算 RRG 象限迁移 ...")
def _rrg_rotation(lookback: int) -> pd.DataFrame:
    return rrg_rotation_table(lookback=lookback)


@st.cache_data(show_spinner="计算历史风险评分 ...")
def _risk_score(top_k: int):
    return risk_score_snapshot(top_k=top_k)


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

# 6-phase color mapping
_PHASE6_KIND = {
    "上行早期": "accent",
    "上行中期": "success",
    "上行晚期": "warning",
    "下行早期": "warning",
    "下行中期": "danger",
    "下行晚期": "danger",
    "震荡":     "muted",
    "n/a":      "muted",
}
snap = _market_state()
phase6_label = snap.phase_6 if snap is not None else None
phase6_kind = _PHASE6_KIND.get(phase6_label, "muted") if phase6_label else "muted"

st.markdown(
    brand_bar(
        trade_date=last_date_str,
        n_stocks=len(u),
        n_themes=len(HOT_CONCEPTS),
        state=phase6_label,
        state_kind=phase6_kind,
    ),
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Hero panel — 6-phase + suggested position + suggested sectors
# ---------------------------------------------------------------------------

if snap is not None:
    st.markdown(
        section_header("市场定位", "6-phase · Position · Resonance sectors"),
        unsafe_allow_html=True,
    )

    h1, h2, h3 = st.columns([1.1, 1.0, 2.0])

    # 1. 当前阶段
    h1.markdown(
        kpi_card(
            "当前阶段",
            pill(snap.phase_6, kind=phase6_kind, size="lg"),
            delta=snap.phase_6_strategy,
        ),
        unsafe_allow_html=True,
    )

    # 2. 建议仓位
    sp = snap.suggested_position
    hint_lo, hint_hi = snap.phase_6_position_hint
    h2.markdown(
        kpi_card(
            "建议仓位",
            f"{sp['score']:.0f}%",
            delta=(
                f"阶段区间 {hint_lo}-{hint_hi}%  ·  "
                f"MA {sp['ma_score']:.0f} / MST {sp['mst_score']:.0f} / CCI {sp['cci_score']:.0f}"
            ),
            accent=True, value_size="xl",
        ),
        unsafe_allow_html=True,
    )

    # 3. 建议板块 (top 5 SC30+SC3 共振)
    if snap.suggested_sectors:
        rows_html = ""
        for s in snap.suggested_sectors[:5]:
            ret5 = s.get("ret_5d")
            ret5s = f"  {ret5:+.1f}%" if ret5 is not None and not pd.isna(ret5) else ""
            rows_html += (
                f"<div style='display:flex;justify-content:space-between;align-items:center;"
                f"padding:5px 0;border-bottom:1px solid var(--border)'>"
                f"<div>"
                f"<span style='color:#E8ECF1;font-size:12.5px;font-weight:600'>{s['concept']}</span>"
                f"  <span style='color:#5F6877;font-size:10.5px;text-transform:uppercase;"
                f"letter-spacing:0.06em'>{s['theme']}</span></div>"
                f"<div style='color:#FF7A87;font-size:11.5px;font-weight:600;"
                f"font-family:JetBrains Mono,monospace;font-variant-numeric:tabular-nums'>"
                f"SC30 {s['sc30']:.0f} · SC3 {s['sc3']:.0f}{ret5s}</div>"
                f"</div>"
            )
        body_html = f"<div style='margin-top:4px'>{rows_html}</div>"
    else:
        body_html = (
            "<div style='color:#5F6877;padding:18px 0;text-align:center;font-size:12px'>"
            "no SC30+SC3 resonance</div>"
        )

    h3.markdown(
        f'<div class="kpi-card">'
        f'<div class="kpi-label">建议板块 · SC30+SC3 共振向上 Top 5</div>'
        f'{body_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main Tabs — 市场 + 个股
# ---------------------------------------------------------------------------

main_tabs = st.tabs(["市场", "个股"])

with main_tabs[0]:
    # --- Market vitals strip ---
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

    tabs = st.tabs([
        "状态",
        "CCI",
        "热力图",
        "排名迁移",
        "容量抱团",
        "象限轮动",
        "周期详情",
        "热度历史",
    ])

    # -------- Sub Tab 0: Market state detail ---------
    with tabs[0]:
        if snap is None:
            st.warning("无法计算市场状态：万得全A 数据缺失。")
        else:
            msc30 = snap.breadth.get("market_sc30")
            msc3 = snap.breadth.get("market_sc3")
            mom5d = snap.breadth.get("market_sc30_5d_mom")

            # Market SC30/SC3/MOM/breadth KPI row
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
            mom_kind = "up" if (mom5d or 0) > 0 else "down"
            ms3.markdown(
                kpi_card("SC30 5日Mom",
                         f"{mom5d:+.1f}" if mom5d is not None else "—",
                         delta="方向 = 趋势加速/减速",
                         delta_kind=mom_kind),
                unsafe_allow_html=True,
            )
            ms4.markdown(
                kpi_card("breadth_ratio",
                         f"{snap.breadth['breadth_ratio']:.2f}",
                         delta=f"↑{snap.breadth['up_count']}  ↓{snap.breadth['down_count']}",
                         delta_kind="up" if snap.breadth['breadth_ratio'] >= 1.0 else "down"),
                unsafe_allow_html=True,
            )

            # 仓位分解
            st.markdown(
                section_header("仓位分解", "MA matrix · MST · CCI weighted"),
                unsafe_allow_html=True,
            )
            sp = snap.suggested_position
            p1, p2, p3, p4 = st.columns(4)
            p1.markdown(
                kpi_card("MA 矩阵分", f"{sp['ma_score']:.0f}",
                         delta="权重 0.5 · 4 主指数站上 MA5/13/50 比例"),
                unsafe_allow_html=True,
            )
            p2.markdown(
                kpi_card("MST 分", f"{sp['mst_score']:.0f}",
                         delta="权重 0.3 · MST5/13/50 均值"),
                unsafe_allow_html=True,
            )
            p3.markdown(
                kpi_card("CCI 分", f"{sp['cci_score']:.0f}",
                         delta=f"权重 0.2 · CCI84 = {snap.position_flex.get('cci84') or '—'}"),
                unsafe_allow_html=True,
            )
            hint_lo, hint_hi = snap.phase_6_position_hint
            p4.markdown(
                kpi_card("加权 = 建议仓位", f"{sp['score']:.1f}",
                         delta=f"阶段区间 {hint_lo}-{hint_hi}%",
                         accent=True),
                unsafe_allow_html=True,
            )

            # ---------- 历史风险评分 ----------
            st.markdown(
                section_header("历史风险评分", "KNN over historical feature snapshots"),
                unsafe_allow_html=True,
            )
            top_k = st.slider("Top-K 相似历史日", min_value=10, max_value=80,
                              value=30, step=5, key="risk_topk")
            rs = _risk_score(int(top_k))
            if rs is None:
                st.info("无历史特征可计算风险评分。")
            else:
                light = risk_light_from_stats(rs.horizons)
                light_kind = {"红": "danger", "黄": "warning", "绿": "success", "n/a": "muted"}.get(light, "muted")

                r1, r2, r3, r4 = st.columns(4)
                r1.markdown(
                    kpi_card(
                        "风险灯",
                        pill(light, kind=light_kind, size="lg"),
                        delta=f"基于 {rs.n_similar} 个最相似历史日",
                    ),
                    unsafe_allow_html=True,
                )
                for col, h in zip((r2, r3, r4), ("1d", "5d", "20d")):
                    s = rs.horizons[h]
                    win = s.get("win_rate", float("nan"))
                    mean = s.get("mean", float("nan"))
                    win_kind = ("up" if not pd.isna(win) and win >= 55
                                else "down" if not pd.isna(win) and win < 45
                                else "muted")
                    col.markdown(
                        kpi_card(
                            f"T+{h} 胜率",
                            f"{win:.1f}%" if not pd.isna(win) else "—",
                            delta=(f"均值 {mean:+.2f}%  ·  "
                                    f"中位 {s.get('median', float('nan')):+.2f}%"
                                    if not pd.isna(mean) else "n/a"),
                            delta_kind=win_kind,
                            accent=(h == "5d"),
                        ),
                        unsafe_allow_html=True,
                    )

                with st.expander(f"Top 15 最相似历史日（含未来 T+1/T+5/T+20 收益）"):
                    sim_df = pd.DataFrame(rs.similar_days)
                    sim_df = sim_df.rename(columns={
                        "distance": "距离",
                        "market_sc30": "SC30",
                        "cci84": "CCI84",
                        "MST_5": "MST5",
                        "breadth_ratio": "breadth",
                        "liquidity_score": "流动性",
                        "ret_1d": "T+1 (%)",
                        "ret_5d": "T+5 (%)",
                        "ret_20d": "T+20 (%)",
                    })
                    sty = sim_df.style \
                        .background_gradient(subset=["T+1 (%)", "T+5 (%)", "T+20 (%)"],
                                              cmap="RdYlGn_r", vmin=-8, vmax=8) \
                        .background_gradient(subset=["距离"], cmap="Blues", vmin=0, vmax=3) \
                        .format({"距离": "{:.2f}", "SC30": "{:.0f}", "CCI84": "{:.0f}",
                                 "MST5": "{:.0f}", "breadth": "{:.2f}",
                                 "流动性": "{:.0f}",
                                 "T+1 (%)": "{:+.2f}",
                                 "T+5 (%)": "{:+.2f}",
                                 "T+20 (%)": "{:+.2f}"})
                    st.dataframe(sty, width="stretch", hide_index=True, height=460)

                st.caption(
                    "**方法**: 把今日 8 维特征（market_sc30 + 5日Mom + MST5/13/50 + "
                    "CCI84 + breadth + 流动性）做 z-score 标准化，按欧氏距离在历史日中找最相似的 Top-K。"
                    "**胜率** = 这 K 个历史日 T+N 全A 涨幅 > 0 的比例。"
                    "**剔除** 最近 30 个交易日，避免与当前窗口重叠。"
                )

            st.markdown(
                section_header("规则与口径", "Methodology"),
                unsafe_allow_html=True,
            )
            st.markdown(
                "- **市场 SC30** = 万得全A 收盘的 30 日 RSV，对标原始框架 SC30 中期\n"
                "- **6 阶段判定**（基于 SC30 + 5日Mom + CCI84 + breadth + 流动性）：\n"
                "  - 上行早期：SC30 < 50，但 5日Mom > 0 且 breadth > 1.0\n"
                "  - 上行中期：SC30 ∈ [50, 75)，5日Mom > 0\n"
                "  - 上行晚期：SC30 ≥ 75，**或** CCI84 > 120 且 breadth < 1.0\n"
                "  - 下行早期：SC30 < 55 且 breadth < 1.0\n"
                "  - 下行中期：SC30 < 40 且 流动性 < 45\n"
                "  - 下行晚期：SC30 < 25 且 breadth < 0.5\n"
                "- **建议仓位** = 0.5 × MA矩阵 + 0.3 × MST + 0.2 × CCI（PDF §7 基础+弹性融合）\n"
                "- **建议板块** = SC30 ≥ 50 且 SC3 ≥ 50 且 5日涨幅 > 0（中期+短期共振向上）\n"
                "- **风险灯**：T+5 胜率 < 40% 或 T+1 均值 < -0.5% → 红；"
                "T+5 胜率 ≥ 60% 且 T+5 均值 > 0.5% → 绿；其它 → 黄"
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
                "超买": "background-color: rgba(230,57,70,0.20); color: #FF7A87; font-weight: 600",
                "偏多": "background-color: rgba(255,176,0,0.18); color: #FFC74D",
                "偏空": "background-color: rgba(6,167,125,0.15); color: #3DD8AE",
                "超卖": "background-color: rgba(6,167,125,0.22); color: #3DD8AE; font-weight: 600",
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
            yaxis=dict(autorange="reversed", color="#E8ECF1"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#E8ECF1", family="Inter"),
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
                "连续": "background-color: rgba(155,164,176,0.12); color: #9BA4B0",
                "新晋": "background-color: rgba(230,57,70,0.20); color: #FF7A87; font-weight: 600",
                "回归": "background-color: rgba(255,176,0,0.18); color: #FFC74D",
                "掉出": "background-color: rgba(6,167,125,0.18); color: #3DD8AE",
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


    # -------- Tab 5: RRG 4-quadrant rotation table ---------
    with tabs[5]:
        st.markdown(
            section_header("板块象限轮动", "4-quadrant rotation · 操作标签"),
            unsafe_allow_html=True,
        )

        col_setting, _ = st.columns([1, 4])
        lookback = col_setting.selectbox(
            "对比窗口（日）", [5, 10, 20], index=1, key="rrg_lookback",
        )

        rot_df = _rrg_rotation(int(lookback))
        if rot_df.empty:
            st.info("无可用 RRG 数据。")
        else:
            # 4 KPI cards by label
            counts = rot_df["rotation_label"].value_counts()
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(
                kpi_card("趋势买入", str(counts.get("趋势买入", 0)),
                         delta="领涨象限 · 持有/加仓", accent=True),
                unsafe_allow_html=True,
            )
            c2.markdown(
                kpi_card("左侧布局", str(counts.get("左侧布局", 0)),
                         delta="转强象限 · 即将进入领涨"),
                unsafe_allow_html=True,
            )
            c3.markdown(
                kpi_card("止盈减仓", str(counts.get("止盈减仓", 0)),
                         delta="转弱象限 · 警惕退潮"),
                unsafe_allow_html=True,
            )
            c4.markdown(
                kpi_card("回避", str(counts.get("回避", 0)),
                         delta="落后象限 · 双弱"),
                unsafe_allow_html=True,
            )

            # Filters
            f1, f2 = st.columns([1, 1])
            sel_theme = f1.multiselect(
                "主题筛选",
                sorted(rot_df["theme"].dropna().unique()),
                key="rrg_rot_theme",
            )
            sel_label = f2.multiselect(
                "操作标签",
                ["趋势买入", "左侧布局", "止盈减仓", "回避"],
                key="rrg_rot_label",
            )
            view = rot_df
            if sel_theme:
                view = view[view["theme"].isin(sel_theme)]
            if sel_label:
                view = view[view["rotation_label"].isin(sel_label)]

            # Render styled table
            show_cols = ["theme", "concept", "rotation_label", "prior_quadrant",
                         "quadrant", "direction", "rs_ratio", "rs_momentum", "ret_5d"]
            disp = view[show_cols].rename(columns={
                "theme": "主题",
                "concept": "概念",
                "rotation_label": "操作",
                "prior_quadrant": f"{lookback}日前",
                "quadrant": "当前",
                "direction": "动向",
                "rs_ratio": "RS-Ratio",
                "rs_momentum": "RS-Mom",
                "ret_5d": "5日(%)",
            })

            label_color = {
                "趋势买入": "background-color: rgba(230,57,70,0.22); color: #FF7A87; font-weight: 600",
                "左侧布局": "background-color: rgba(255,176,0,0.22); color: #FFC74D; font-weight: 600",
                "止盈减仓": "background-color: rgba(6,167,125,0.22); color: #3DD8AE; font-weight: 600",
                "回避":     "background-color: rgba(155,164,176,0.12); color: #9BA4B0; font-weight: 600",
            }
            quadrant_color = {
                "领涨": "background-color: rgba(230,57,70,0.18); color: #FF7A87",
                "转强": "background-color: rgba(255,176,0,0.18); color: #FFC74D",
                "转弱": "background-color: rgba(74,143,231,0.18); color: #7FB3F2",
                "落后": "background-color: rgba(6,167,125,0.18); color: #3DD8AE",
                "n/a":  "color: #5F6877",
            }
            direction_color = {
                "改善": "color: #FF7A87; font-weight: 600",
                "维持": "color: #9BA4B0",
                "恶化": "color: #3DD8AE; font-weight: 600",
            }
            sty = disp.style \
                .applymap(lambda v: label_color.get(v, ""), subset=["操作"]) \
                .applymap(lambda v: quadrant_color.get(v, ""),
                          subset=[f"{lookback}日前", "当前"]) \
                .applymap(lambda v: direction_color.get(v, ""), subset=["动向"]) \
                .background_gradient(subset=["RS-Ratio", "RS-Mom"],
                                      cmap="RdYlGn_r", vmin=-3, vmax=3) \
                .background_gradient(subset=["5日(%)"], cmap="RdYlGn_r", vmin=-10, vmax=10) \
                .format({"RS-Ratio": "{:.2f}", "RS-Mom": "{:.2f}", "5日(%)": "{:.2f}"})
            st.dataframe(sty, width="stretch", hide_index=True, height=560)

            st.caption(
                "**操作标签** 由当前象限决定：领涨→趋势买入 · 转强→左侧布局 · 转弱→止盈减仓 · 落后→回避。"
                f"**动向** 比较 {lookback} 日前与今日的象限质量（领涨>转强>转弱>落后）。"
                "**RS-Ratio** = (板块/沪深300) 60 日滚动 Z-score。"
                "**RS-Mom** = RS-Ratio 5 日变化的 60 日滚动 Z-score。"
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
            "偏热":  "background-color: rgba(230,57,70,0.22); color: #FF7A87; font-weight: 600",
            "强势":  "background-color: rgba(255,176,0,0.20); color: #FFC74D",
            "中性":  "background-color: rgba(155,164,176,0.10); color: #9BA4B0",
            "冰点":  "background-color: rgba(6,167,125,0.20); color: #3DD8AE",
        }
        phase_color = {
            "高潮":   "background-color: rgba(230,57,70,0.26); color: #FF8794; font-weight: 600",
            "高位回调": "background-color: rgba(255,176,0,0.22); color: #FFC74D",
            "强势":   "background-color: rgba(255,176,0,0.18); color: #FFC74D",
            "抱团":   "background-color: rgba(230,57,70,0.16); color: #FF7A87",
            "酝酿反弹": "background-color: rgba(74,143,231,0.18); color: #7FB3F2",
            "酝酿":   "background-color: rgba(155,164,176,0.12); color: #9BA4B0",
            "底部反弹": "background-color: rgba(74,143,231,0.20); color: #7FB3F2",
            "冰点":   "background-color: rgba(6,167,125,0.20); color: #3DD8AE",
        }
        sty = view[show_cols].style \
            .applymap(lambda v: strength_color.get(v, ""), subset=["strength"]) \
            .applymap(lambda v: phase_color.get(v, ""), subset=["phase"]) \
            .background_gradient(subset=["SC30", "SC3", "SC60", "heat"],
                                  cmap="RdYlGn_r", vmin=0, vmax=100) \
            .background_gradient(subset=["ret_5d", "ret_20d"], cmap="RdYlGn_r", vmin=-15, vmax=15) \
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
                fig.update_layout(
                    height=520, hovermode="x unified",
                    margin=dict(l=20, r=20, t=20, b=20),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#E8ECF1", family="Inter"),
                    xaxis=dict(gridcolor="#232830", color="#9BA4B0"),
                    yaxis=dict(gridcolor="#232830", color="#9BA4B0"),
                    legend=dict(font=dict(color="#E8ECF1")),
                )
                st.plotly_chart(fig, width="stretch")


def _placeholder_card(title: str, subtitle: str, items: list[str]) -> str:
    items_html = "".join(
        f'<li style="margin:6px 0;color:#9BA4B0;font-size:12.5px;line-height:1.6">{x}</li>'
        for x in items
    )
    return (
        f'<div class="kpi-card" style="padding:18px 20px">'
        f'<div style="font-size:14px;font-weight:700;color:#E8ECF1;'
        f'text-transform:uppercase;letter-spacing:0.14em">{title}</div>'
        f'<div style="font-size:10.5px;color:#5F6877;margin-top:4px;'
        f'text-transform:uppercase;letter-spacing:0.1em">{subtitle}</div>'
        f'<div style="margin-top:14px;'
        f'padding:3px 10px;background:rgba(255,176,0,0.10);'
        f'border:1px solid rgba(255,176,0,0.35);border-radius:2px;'
        f'color:#FFB000;font-size:10.5px;font-weight:600;'
        f'text-transform:uppercase;letter-spacing:0.12em;'
        f'display:inline-block">COMING SOON</div>'
        f'<ul style="margin:14px 0 0 18px;padding:0">{items_html}</ul>'
        f'</div>'
    )


# -------- Main Tab 2: 个股 ---------
with main_tabs[1]:
    col_input, _ = st.columns([1, 3])
    stock_input = col_input.text_input(
        "输入股票代码",
        value="000001.XSHE",
        placeholder="例如: 000001.XSHE 或 000001.SZ",
    )

    stk_tabs = st.tabs([
        "标签",
        "量化指标",
        "研报",
        "产业图",
        "Wiki",
    ])

    # ---------- 标签 (existing tag engine) ----------
    with stk_tabs[0]:
        if not stock_input:
            st.info("请输入股票代码")
        else:
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
                    # (fg, bg) — semi-transparent backgrounds tint over the dark card
                    _RED   = ("#FF7A87", "rgba(230,57,70,0.20)")
                    _AMBER = ("#FFC74D", "rgba(255,176,0,0.20)")
                    _GREEN = ("#3DD8AE", "rgba(6,167,125,0.20)")
                    _BLUE  = ("#7FB3F2", "rgba(74,143,231,0.20)")
                    _GRAY  = ("#9BA4B0", "rgba(155,164,176,0.10)")
                    tag_color = {
                        # 现有
                        "主线核心":       _RED,
                        "容量焦点":       _AMBER,
                        "强趋势":         _AMBER,
                        "高拥挤":         _RED,
                        "回调观察":       _BLUE,
                        "超跌反弹":       _GREEN,
                        "右侧确认":       _RED,
                        "放量突破":       _AMBER,
                        "涨停基因":       _RED,
                        "缩量回调":       _GRAY,
                        # §10.5 趋势卡位
                        "趋势卡位买点":   _AMBER,
                        "趋势卡位精选":   _RED,
                        # §10.6 5层抄底
                        "抄底·绝底(95)": _GREEN,
                        "抄底·超高(87)": _GREEN,
                        "抄底·高(81)":   _AMBER,
                        "抄底·中高(68)": _BLUE,
                        "抄底·中(60)":   _GRAY,
                        # §10.7 情绪龙头
                        "涨停":           _RED,
                        "夺命板":         _RED,
                        "攻击资金共振":   _AMBER,
                    }
                    badge_html = ""
                    for tag in tags:
                        # 连板·N板 / 连板·2板 etc. all share color
                        color_key = "涨停" if tag.startswith("连板·") else tag
                        fg, bg = tag_color.get(color_key, _GRAY)
                        badge_html += (
                            f'<span style="background-color:{bg};color:{fg};'
                            f'padding:3px 10px;border-radius:2px;margin:3px;'
                            f'font-weight:600;font-size:11.5px;'
                            f'text-transform:uppercase;letter-spacing:0.04em;'
                            f'border:1px solid {fg}33;'
                            f'display:inline-block">'
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
                    col.metric(name, "ABOVE" if on else "BELOW")

                # RRG (vs 沪深300)
                from einvest.io import load_stock as _load_stk
                stk_df = _load_stk(result["code"])
                if not stk_df.empty:
                    close_s = stk_df.set_index("date")["close"].sort_index()
                    rrg_info = stock_rrg(close_s)
                    ma_cols[3].metric(
                        "RRG 象限",
                        rrg_info["quadrant"],
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

    # ---------- 量化指标 (placeholder) ----------
    with stk_tabs[1]:
        st.markdown(f"### 量化指标 · {stock_input or '—'}")
        st.markdown(
            _placeholder_card(
                "量化指标体系",
                "Factor exposures · Risk metrics",
                [
                    "<b>因子暴露</b>：价值 / 成长 / 动量 / 质量 / 波动率 / 规模 6 大风格因子打分",
                    "<b>多因子排名</b>：在所属概念 / 行业 / 全市场的截面分位",
                    "<b>风险指标</b>：年化波动 · 最大回撤 · Sharpe / Calmar · Beta vs 沪深300",
                    "<b>资金面</b>：北向持股变动 / 融资余额 / 大单净流入 (Lv2 数据接入后)",
                    "<b>事件信号</b>：业绩预告 / 分红除权 / 解禁 / 减持公告",
                ],
            ),
            unsafe_allow_html=True,
        )

    # ---------- 研报 (placeholder) ----------
    with stk_tabs[2]:
        st.markdown(f"### 卖方研报 · {stock_input or '—'}")
        st.markdown(
            _placeholder_card(
                "研报聚合",
                "Sell-side research · Foreign IB views",
                [
                    "<b>评级一致性</b>：中信/中金/华泰 等内资 + 高盛/摩根 等外资 评级分布",
                    "<b>目标价区间</b>：N 家机构目标价均值 / 中位数 · 距现价空间",
                    "<b>盈利预测变动</b>：未来 12 个月 EPS 一致预期 30/60/90 天变动",
                    "<b>最新研报摘要</b>：近 30 日新发研报标题 · 核心观点 · PDF 链接",
                    "<b>北向 vs 卖方背离</b>：评级上调但北向减持 / 反之 → 信号点",
                ],
            ),
            unsafe_allow_html=True,
        )

    # ---------- 产业图 (placeholder) ----------
    with stk_tabs[3]:
        st.markdown(f"### 产业链图 · {stock_input or '—'}")
        st.markdown(
            _placeholder_card(
                "产业链定位",
                "Industry value chain · Peer mapping",
                [
                    "<b>所在产业链位置</b>：上游原材料 / 中游制造 / 下游应用 节点定位",
                    "<b>上游供应商</b>：核心原材料 / 设备 / 零部件 提供商及其股价联动",
                    "<b>下游客户</b>：主要客户构成 · 客户集中度 · 客户股价表现",
                    "<b>同业竞争对手</b>：核心 peer 列表 · 营收/利润/估值横向对比",
                    "<b>替代品 / 互补品</b>：技术路线 / 应用替代关系图谱",
                ],
            ),
            unsafe_allow_html=True,
        )

    # ---------- Wiki (placeholder) ----------
    with stk_tabs[4]:
        st.markdown(f"### Wiki · {stock_input or '—'}")
        st.markdown(
            _placeholder_card(
                "公司画像",
                "Business overview · KPI snapshot",
                [
                    "<b>公司简介</b>：主营业务 / 控股股东 / 上市时间 / 注册地",
                    "<b>核心业务收入结构</b>：分业务 / 分区域 收入占比 · 同比",
                    "<b>关键运营指标</b>：行业 KPI（产能利用率 / 出货量 / ARPU 等）",
                    "<b>核心管理层</b>：董事长 / CEO / CFO 背景 + 持股变动",
                    "<b>市场关注题材</b>：最近被资金炒作的故事线 · 相关概念板块",
                ],
            ),
            unsafe_allow_html=True,
        )
