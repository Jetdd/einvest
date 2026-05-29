"""Per-indicator conditional backtest (蒸馏 §4.2 + §7).

For each indicator, buckets the historical panel by the indicator's value,
then computes T+1/T+5/T+20 win_rate / payoff_ratio / mean for the bucket
that contains the current day's value.

Also provides a market-phase backtest: for the current 6-phase classification,
find all historical days in the same phase and compute forward return stats.

Output feeds the dashboard's "信号回测" table (replicating the PDF's
"市场风险评分" grid: rows=indicators, cols=1d/5d/20d stats + sample count).
"""
from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .market_state import market_phase_6
from .risk_score import _feature_panel, HORIZONS, _horizon_stats, find_similar_days, FEATURES


# ---------------------------------------------------------------------------
# Indicator bucket definitions
# ---------------------------------------------------------------------------

# Each entry: (lo, hi, label)  — half-open [lo, hi)
_SC_BUCKETS = [
    (-np.inf, 25, "冰点"),
    (25,       40, "低位"),
    (40,       60, "中位"),
    (60,       75, "高位"),
    (75,  np.inf,  "顶部"),
]

_MST_BUCKETS = [
    (-np.inf, 25, "<25"),
    (25,       40, "25-40"),
    (40,       60, "40-60"),
    (60,       75, "60-75"),
    (75,  np.inf,  ">75"),
]

_CCI_BUCKETS = [
    (-np.inf, -100, "超卖"),
    (-100,       0, "中性偏空"),
    (0,         80, "中性偏多"),
    (80,   np.inf,  "超买"),
]

_LIQ_BUCKETS = [
    (-np.inf, 35, "冷清"),
    (35,       45, "偏冷"),
    (45,       90, "充足"),
    (90,  np.inf,  "过热"),
]

_BREADTH_BUCKETS = [
    (-np.inf, 0.5, "极弱"),
    (0.5,     0.8, "偏弱"),
    (0.8,     1.2, "均衡"),
    (1.2,     2.0, "偏强"),
    (2.0, np.inf,  "极强"),
]

_MOM_BUCKETS = [
    (-np.inf, -5, "下行强"),
    (-5,       -1, "下行"),
    (-1,        1, "平稳"),
    (1,         5, "上行"),
    (5,   np.inf,  "上行强"),
]

# display_name → (feature_col, buckets, format_str)
INDICATOR_CONFIG: dict[str, tuple[str, list, str]] = {
    "SC30":    ("market_sc30",        _SC_BUCKETS,      "{:.0f}"),
    "SC30动量": ("market_sc30_5d_mom", _MOM_BUCKETS,     "{:+.1f}"),
    "MST5":    ("MST_5",              _MST_BUCKETS,     "{:.0f}"),
    "MST50":   ("MST_50",             _MST_BUCKETS,     "{:.0f}"),
    "CCI短期":  ("cci14",              _CCI_BUCKETS,     "{:.0f}"),
    "CCI长期":  ("cci84",              _CCI_BUCKETS,     "{:.0f}"),
    "流动性":   ("liquidity_score",    _LIQ_BUCKETS,     "{:.0f}"),
}


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _classify(value: float, buckets: list) -> tuple[str, float, float]:
    """Return (label, lo, hi) for the bucket that contains `value`."""
    for lo, hi, label in buckets:
        if lo <= value < hi:
            return label, lo, hi
    return "n/a", -np.inf, np.inf


def _payoff_ratio(rets: pd.Series) -> float:
    """avg_win / |avg_loss|. NaN if either side is empty."""
    rets = rets.dropna()
    wins   = rets[rets > 0]
    losses = rets[rets < 0]
    if wins.empty or losses.empty:
        return float("nan")
    return float(wins.mean() / abs(losses.mean()))


def _stats_for_subset(subset: pd.DataFrame) -> dict[str, dict[str, float]]:
    """T+1/T+5/T+20 stats dict for a historical subset."""
    out: dict[str, dict[str, float]] = {}
    for h in HORIZONS:
        col = f"ret_{h}d"
        if col not in subset.columns:
            out[f"{h}d"] = {"win_rate": float("nan"), "mean": float("nan"),
                             "payoff": float("nan"), "n": 0}
            continue
        rets = subset[col].dropna()
        base = _horizon_stats(rets)
        base["payoff"] = _payoff_ratio(rets)
        out[f"{h}d"] = base
    return out


# ---------------------------------------------------------------------------
# Per-indicator conditional backtest
# ---------------------------------------------------------------------------

@dataclass
class IndicatorRow:
    name: str            # display name
    feature: str         # column name in panel
    current_value: float
    bucket: str          # which bucket the current value falls into
    stats: dict[str, dict[str, float]]  # {horizon: {win_rate, mean, payoff, n}}


_FEATURE_TO_BUCKETS: dict[str, list] = {
    feature: bkt_list
    for _, (feature, bkt_list, _) in INDICATOR_CONFIG.items()
}

_FEATURE_TO_FMT: dict[str, str] = {
    feature: fmt
    for _, (feature, _, fmt) in INDICATOR_CONFIG.items()
}


def _indicator_row(
    name: str,
    feature: str,
    current: pd.Series,
    panel: pd.DataFrame,
) -> IndicatorRow:
    val = float(current.get(feature, float("nan")))
    if pd.isna(val) or feature not in panel.columns:
        return IndicatorRow(name=name, feature=feature, current_value=val,
                            bucket="n/a", stats={})

    bkt_list = _FEATURE_TO_BUCKETS[feature]
    label, lo, hi = _classify(val, bkt_list)

    mask = (panel[feature] >= lo) & (panel[feature] < hi)
    subset = panel[mask]
    stats = _stats_for_subset(subset)
    return IndicatorRow(name=name, feature=feature, current_value=val,
                        bucket=label, stats=stats)


# ---------------------------------------------------------------------------
# Phase backtest
# ---------------------------------------------------------------------------

def _phase_backtest(panel: pd.DataFrame) -> dict[str, Any]:
    """Find all historical days in the same 6-phase and compute return stats."""
    required = ["market_sc30", "market_sc30_5d_mom", "cci84", "breadth_ratio", "liquidity_score"]
    if not all(c in panel.columns for c in required):
        return {}

    # Vectorise market_phase_6 over history
    phases = panel.apply(
        lambda r: market_phase_6(
            market_sc30=r["market_sc30"],
            market_sc30_5d_mom=r["market_sc30_5d_mom"],
            cci84=r["cci84"],
            breadth_ratio=r["breadth_ratio"],
            liquidity_score=r["liquidity_score"],
        ),
        axis=1,
    )

    current_phase = phases.iloc[-1]
    subset = panel[phases == current_phase].iloc[:-1]  # exclude today
    stats = _stats_for_subset(subset)
    return {
        "phase": current_phase,
        "n": int(len(subset)),
        "stats": stats,
    }


# ---------------------------------------------------------------------------
# Full snapshot
# ---------------------------------------------------------------------------

@dataclass
class SignalBacktestSnapshot:
    date: str
    indicators: list[IndicatorRow]
    phase_backtest: dict[str, Any]
    knn_stats: dict[str, dict[str, float]]   # from existing KNN
    knn_n: int


@functools.cache
def signal_backtest_snapshot(*, top_k: int = 30) -> SignalBacktestSnapshot | None:
    panel = _feature_panel()
    if panel.empty:
        return None

    feat_only = panel[FEATURES].dropna()
    if feat_only.empty:
        return None

    cur_date = feat_only.index[-1]
    current = feat_only.iloc[-1]

    # Per-indicator rows (exclude today from the history panel)
    hist = panel.iloc[:-1]
    rows: list[IndicatorRow] = []
    for name, (feature, _, _fmt) in INDICATOR_CONFIG.items():
        rows.append(_indicator_row(name, feature, current, hist))

    # Phase backtest
    phase_bt = _phase_backtest(panel)

    # KNN stats (reuse existing logic)
    similar = find_similar_days(current, panel, top_k=top_k, exclude_last_n=30)
    knn_stats: dict[str, dict[str, float]] = {}
    for h in HORIZONS:
        rets = similar[f"ret_{h}d"]
        base = _horizon_stats(rets)
        base["payoff"] = _payoff_ratio(rets)
        knn_stats[f"{h}d"] = base

    return SignalBacktestSnapshot(
        date=cur_date.date().isoformat(),
        indicators=rows,
        phase_backtest=phase_bt,
        knn_stats=knn_stats,
        knn_n=int(len(similar)),
    )


def clear_signal_backtest_cache() -> None:
    signal_backtest_snapshot.cache_clear()


# ---------------------------------------------------------------------------
# DataFrame builder for dashboard display
# ---------------------------------------------------------------------------

def backtest_table_df(snap: SignalBacktestSnapshot) -> pd.DataFrame:
    """Build a DataFrame suitable for st.dataframe display.

    Columns: 指标, 当前值, 区间, 1d胜率%, 1d赔权, 5d胜率%, 5d赔权,
             20d胜率%, 20d均值%, 20d赔权, 样本
    """
    recs = []
    for row in snap.indicators:
        cur_str = (_FEATURE_TO_FMT.get(row.feature, "{:.1f}").format(row.current_value)
                   if not pd.isna(row.current_value) else "—")
        s1 = row.stats.get("1d", {})
        s5 = row.stats.get("5d", {})
        s20 = row.stats.get("20d", {})
        recs.append({
            "指标":      row.name,
            "当前值":    cur_str,
            "区间":      row.bucket,
            "1d胜率%":   s1.get("win_rate", float("nan")),
            "1d赔权":    s1.get("payoff",   float("nan")),
            "5d胜率%":   s5.get("win_rate", float("nan")),
            "5d赔权":    s5.get("payoff",   float("nan")),
            "20d胜率%":  s20.get("win_rate", float("nan")),
            "20d均值%":  s20.get("mean",    float("nan")),
            "20d赔权":   s20.get("payoff",  float("nan")),
            "样本":      s1.get("n", 0),
        })

    # KNN综合相似 row
    s1  = snap.knn_stats.get("1d",  {})
    s5  = snap.knn_stats.get("5d",  {})
    s20 = snap.knn_stats.get("20d", {})
    recs.append({
        "指标":      "★ 综合相似",
        "当前值":    "",
        "区间":      f"KNN Top-{snap.knn_n}",
        "1d胜率%":   s1.get("win_rate", float("nan")),
        "1d赔权":    s1.get("payoff",   float("nan")),
        "5d胜率%":   s5.get("win_rate", float("nan")),
        "5d赔权":    s5.get("payoff",   float("nan")),
        "20d胜率%":  s20.get("win_rate", float("nan")),
        "20d均值%":  s20.get("mean",    float("nan")),
        "20d赔权":   s20.get("payoff",  float("nan")),
        "样本":      snap.knn_n,
    })

    return pd.DataFrame(recs)
