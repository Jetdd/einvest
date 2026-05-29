"""Relative Rotation Graph (蒸馏 §3.5).

Per concept (vs benchmark, default 沪深300):

  rs_ratio    : Z-score of (sector_close / benchmark_close) over rolling window
                centered at 0, scaled so most values fall in ±2.
  rs_momentum : Z-score of rs_ratio.diff(5) (the rate of change of relative
                strength) over the same window.

Quadrants (sign convention):
  rs_ratio ≥ 0 ∧ rs_momentum ≥ 0  →  领涨 (Leading)
  rs_ratio ≥ 0 ∧ rs_momentum < 0  →  转弱 (Weakening)
  rs_ratio < 0 ∧ rs_momentum < 0  →  落后 (Lagging)
  rs_ratio < 0 ∧ rs_momentum ≥ 0  →  转强 (Improving)

The same method applies to individual stocks (close panel vs benchmark).
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from .io import load_index
from .rankings import sector_close_panel
from .sectors import BENCHMARKS, HOT_CONCEPTS


# ---------------------------------------------------------------------------
# Core calc
# ---------------------------------------------------------------------------

def _zscore(s: pd.Series, window: int) -> pd.Series:
    """Rolling Z-score."""
    mean = s.rolling(window, min_periods=max(20, window // 3)).mean()
    std = s.rolling(window, min_periods=max(20, window // 3)).std(ddof=0)
    return (s - mean) / std.replace(0, np.nan)


def rs_ratio(sector_close: pd.Series, benchmark_close: pd.Series,
              window: int = 60) -> pd.Series:
    """JdK-style RS-Ratio (rolling Z-score of ratio)."""
    bench = benchmark_close.reindex(sector_close.index).ffill()
    ratio = sector_close / bench.where(bench > 0, np.nan)
    return _zscore(ratio, window)


def rs_momentum(rs: pd.Series, *, diff_period: int = 5,
                 window: int = 60) -> pd.Series:
    """RS-Momentum = Z-score of RS-Ratio's `diff_period`-day change."""
    return _zscore(rs.diff(diff_period), window)


def classify_quadrant(rs: float, mom: float) -> str:
    if pd.isna(rs) or pd.isna(mom):
        return "n/a"
    if rs >= 0 and mom >= 0:
        return "领涨"
    if rs >= 0 and mom < 0:
        return "转弱"
    if rs < 0 and mom < 0:
        return "落后"
    return "转强"


# ---------------------------------------------------------------------------
# Rotation labels — current quadrant → 4 operating tags
# ---------------------------------------------------------------------------

ROTATION_LABEL: dict[str, str] = {
    "领涨": "趋势买入",
    "转强": "左侧布局",
    "转弱": "止盈减仓",
    "落后": "回避",
    "n/a":  "—",
}

# Heuristic quadrant quality ordering used to derive 动向 (改善/维持/恶化).
# Cycle: 转强 → 领涨 → 转弱 → 落后 → 转强 …  (counter-clockwise quality drift).
_QUADRANT_RANK: dict[str, int] = {"领涨": 3, "转强": 2, "转弱": 1, "落后": 0, "n/a": -1}


# A concept is 临界 (on the edge) when one RRG axis sits within ±band of 0,
# so one more session can flip the quadrant — and thus the operation label.
CRITICAL_BAND = 0.35


def rotation_critical(rs: float, mom: float) -> tuple[bool, str]:
    """Whether (rs, mom) sits near a quadrant boundary.

    Returns (is_critical, would-be label) — the operation label the concept
    would take if the nearest-to-zero axis flips sign. Since each quadrant maps
    to a distinct label, the would-be label always differs from the current one.
    """
    if pd.isna(rs) or pd.isna(mom):
        return False, ""
    near_mom = abs(mom) < CRITICAL_BAND
    near_rs = abs(rs) < CRITICAL_BAND
    if not (near_mom or near_rs):
        return False, ""
    # Flip whichever axis is closest to its zero boundary.
    if near_mom and (not near_rs or abs(mom) <= abs(rs)):
        new_q = classify_quadrant(rs, -1.0 if mom >= 0 else 1.0)
    else:
        new_q = classify_quadrant(-1.0 if rs >= 0 else 1.0, mom)
    return True, ROTATION_LABEL.get(new_q, "—")


def rotation_direction(prior: str, current: str) -> str:
    """Improvement direction between two quadrants.

    改善 = quality rank went up, 恶化 = went down, 维持 = unchanged.
    n/a sides => "—".
    """
    a, b = _QUADRANT_RANK.get(prior, -1), _QUADRANT_RANK.get(current, -1)
    if a < 0 or b < 0:
        return "—"
    if b > a:
        return "改善"
    if b < a:
        return "恶化"
    return "维持"


# ---------------------------------------------------------------------------
# Per-concept latest + trail
# ---------------------------------------------------------------------------

def rrg_latest_per_concept(
    *,
    benchmark: str = "000300.XSHG",
    window: int = 60,
    diff_period: int = 5,
    trail_length: int = 5,
    concepts: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Latest RRG snapshot + last `trail_length` points per concept.

    Columns: theme, concept, rs_ratio, rs_momentum, quadrant, trail_rs, trail_mom
    Trails are returned as lists for plotting the path.
    """
    bench_df = load_index(benchmark)
    if bench_df.empty:
        return pd.DataFrame()
    bench = bench_df.set_index("date")["close"].sort_index()

    panel = sector_close_panel(concepts)
    if panel.empty:
        return pd.DataFrame()

    theme_lookup = {c: theme for theme, items in HOT_CONCEPTS.items() for c in items}

    rows: list[dict] = []
    for concept in panel.columns:
        s = panel[concept].dropna()
        if len(s) < window + diff_period:
            continue
        rs = rs_ratio(s, bench, window=window)
        mom = rs_momentum(rs, diff_period=diff_period, window=window)
        cur_rs = float(rs.iloc[-1]) if not pd.isna(rs.iloc[-1]) else float("nan")
        cur_mom = float(mom.iloc[-1]) if not pd.isna(mom.iloc[-1]) else float("nan")

        trail_rs = [float(v) if not pd.isna(v) else None
                    for v in rs.tail(trail_length).values]
        trail_mom = [float(v) if not pd.isna(v) else None
                     for v in mom.tail(trail_length).values]

        rows.append({
            "theme": theme_lookup.get(concept),
            "concept": concept,
            "rs_ratio": round(cur_rs, 3) if not pd.isna(cur_rs) else None,
            "rs_momentum": round(cur_mom, 3) if not pd.isna(cur_mom) else None,
            "quadrant": classify_quadrant(cur_rs, cur_mom),
            "trail_rs": trail_rs,
            "trail_mom": trail_mom,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Per-stock RRG (single point, no trail)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Rotation table — current + prior quadrant + label per concept
# ---------------------------------------------------------------------------

def rrg_rotation_table(
    *,
    benchmark: str = "000300.XSHG",
    window: int = 60,
    diff_period: int = 5,
    lookback: int = 10,
    concepts: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Per-concept RRG snapshot with prior quadrant + rotation label.

    Columns: theme, concept, rs_ratio, rs_momentum, quadrant,
             prior_quadrant, direction, rotation_label, ret_5d.
    """
    bench_df = load_index(benchmark)
    if bench_df.empty:
        return pd.DataFrame()
    bench = bench_df.set_index("date")["close"].sort_index()

    panel = sector_close_panel(concepts)
    if panel.empty:
        return pd.DataFrame()

    theme_lookup = {c: theme for theme, items in HOT_CONCEPTS.items() for c in items}

    rows: list[dict] = []
    for concept in panel.columns:
        s = panel[concept].dropna()
        if len(s) < window + diff_period + lookback:
            continue
        rs = rs_ratio(s, bench, window=window)
        mom = rs_momentum(rs, diff_period=diff_period, window=window)
        cur_rs = float(rs.iloc[-1]) if not pd.isna(rs.iloc[-1]) else float("nan")
        cur_mom = float(mom.iloc[-1]) if not pd.isna(mom.iloc[-1]) else float("nan")
        curr_q = classify_quadrant(cur_rs, cur_mom)

        prior_idx = -lookback - 1
        if abs(prior_idx) > len(rs):
            prior_q = "n/a"
        else:
            prior_rs = rs.iloc[prior_idx]
            prior_mom = mom.iloc[prior_idx]
            prior_q = classify_quadrant(
                float(prior_rs) if not pd.isna(prior_rs) else float("nan"),
                float(prior_mom) if not pd.isna(prior_mom) else float("nan"),
            )

        ret_5d = (float(s.iloc[-1] / s.iloc[-6] - 1) * 100
                  if len(s) > 5 else float("nan"))
        ret_1d = (float(s.iloc[-1] / s.iloc[-2] - 1) * 100
                  if len(s) > 1 else float("nan"))

        is_crit, crit_to = rotation_critical(cur_rs, cur_mom)

        rows.append({
            "theme": theme_lookup.get(concept),
            "concept": concept,
            "rs_ratio": round(cur_rs, 2) if not pd.isna(cur_rs) else None,
            "rs_momentum": round(cur_mom, 2) if not pd.isna(cur_mom) else None,
            "quadrant": curr_q,
            "prior_quadrant": prior_q,
            "direction": rotation_direction(prior_q, curr_q),
            "rotation_label": ROTATION_LABEL.get(curr_q, "—"),
            "critical": is_crit,
            "critical_to": crit_to,
            "ret_1d": round(ret_1d, 2) if not pd.isna(ret_1d) else None,
            "ret_5d": round(ret_5d, 2) if not pd.isna(ret_5d) else None,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # Sort by label (买/布局 first), then rs_ratio desc
    label_order = {"趋势买入": 0, "左侧布局": 1, "止盈减仓": 2, "回避": 3, "—": 4}
    df["_label_rank"] = df["rotation_label"].map(label_order).fillna(4)
    df = df.sort_values(["_label_rank", "rs_ratio"], ascending=[True, False])
    return df.drop(columns="_label_rank").reset_index(drop=True)


def stock_rrg(stock_close: pd.Series, *,
               benchmark: str = "000300.XSHG",
               window: int = 60,
               diff_period: int = 5) -> dict:
    """Latest RRG point for one stock vs benchmark."""
    bench_df = load_index(benchmark)
    if bench_df.empty or stock_close.empty or len(stock_close) < window + diff_period:
        return {"rs_ratio": None, "rs_momentum": None, "quadrant": "n/a",
                "benchmark": benchmark}
    bench = bench_df.set_index("date")["close"].sort_index()
    rs = rs_ratio(stock_close, bench, window=window)
    mom = rs_momentum(rs, diff_period=diff_period, window=window)
    cur_rs = float(rs.iloc[-1]) if not pd.isna(rs.iloc[-1]) else float("nan")
    cur_mom = float(mom.iloc[-1]) if not pd.isna(mom.iloc[-1]) else float("nan")
    return {
        "rs_ratio": round(cur_rs, 3) if not pd.isna(cur_rs) else None,
        "rs_momentum": round(cur_mom, 3) if not pd.isna(cur_mom) else None,
        "quadrant": classify_quadrant(cur_rs, cur_mom),
        "benchmark": benchmark,
    }
