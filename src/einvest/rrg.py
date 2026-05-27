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
