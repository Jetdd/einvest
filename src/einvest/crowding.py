"""容量抱团框架（蒸馏 §3.4 + §11）.

Per concept:
  top_n_amount      : top N 成份股成交额合计（元）
  share_pct         : top_n_amount / 全市场成交额 × 100
  strength_pct      : share_pct 在过去 60 日的滚动百分位 (0-100)
  peak_share_60d    : 过去 60 日的 share 峰值
  decay_pct         : (peak - current) / peak × 100，越大说明远离峰值
  days_in_top7      : 在 5 日涨幅 Top7 中连续天数

Market-level:
  top_theme_share   : 最大的 concept 的 share_pct
  abs_crowding      : top_theme_share 是否超过历史 90% 分位（绝对抱团信号）

Per-stock:
  is_capacity_focus : 个股在某个 Top7 主题里的 top3 成交额 → "容量焦点" tag
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from .io import constituents, load_full_a, load_panel
from .rankings import n_day_return, sector_close_panel
from .sectors import HOT_CONCEPTS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _top_n_sum(panel: pd.DataFrame, n: int) -> pd.Series:
    """For each row, sum the top-N non-NaN values. Numpy-vectorised."""
    if panel.empty:
        return pd.Series(dtype=float, index=panel.index)
    arr = panel.to_numpy(dtype=float, copy=False)
    # NaN → -inf so they sort to the bottom in np.partition
    arr_filled = np.where(np.isnan(arr), -np.inf, arr)
    cols = arr.shape[1]
    if cols == 0:
        return pd.Series(np.nan, index=panel.index)
    k = min(n, cols)
    # Partition so the top-k values are in the last k columns (unsorted)
    partitioned = np.partition(arr_filled, cols - k, axis=1)
    top_vals = partitioned[:, cols - k:]
    # Replace -inf (came from NaN) with 0 so sum is the top-k positive amounts
    top_vals = np.where(np.isneginf(top_vals), 0.0, top_vals)
    # Rows with all NaN → sum 0; flag those back to NaN
    all_nan = np.all(np.isnan(arr), axis=1)
    out = top_vals.sum(axis=1)
    out[all_nan] = np.nan
    return pd.Series(out, index=panel.index)


def _days_in_top7(rets5: pd.DataFrame, concept: str, k: int = 7) -> int:
    """Consecutive sessions concept was in top-k by 5-day return, counting back."""
    if rets5.empty or concept not in rets5.columns:
        return 0
    days = 0
    for i in range(len(rets5) - 1, -1, -1):
        row = rets5.iloc[i].dropna()
        if row.empty:
            break
        top = row.sort_values(ascending=False).head(k).index
        if concept in top:
            days += 1
        else:
            break
    return days


# ---------------------------------------------------------------------------
# Concept-level crowding
# ---------------------------------------------------------------------------

def _concept_metrics(amt_panel: pd.DataFrame, market_amt: pd.Series,
                       top_n: int) -> pd.DataFrame:
    """Compute time series of crowding metrics from a concept's amount panel."""
    if amt_panel.empty:
        return pd.DataFrame()
    top_sum = _top_n_sum(amt_panel, top_n)
    market_amt_aligned = market_amt.reindex(top_sum.index).ffill()
    share = (top_sum / market_amt_aligned.where(market_amt_aligned > 0, np.nan)) * 100
    strength = share.rolling(60, min_periods=20).rank(pct=True) * 100
    peak60 = share.rolling(60, min_periods=1).max()
    decay = (peak60 - share) / peak60.where(peak60 > 0, np.nan) * 100
    return pd.DataFrame({
        "top_n_amount": top_sum,
        "share_pct": share,
        "strength_pct": strength,
        "peak_share_60d": peak60,
        "decay_pct": decay,
    })


def concept_crowding_history(concept: str,
                              market_amt: pd.Series,
                              top_n: int = 5) -> pd.DataFrame:
    """Time series of crowding metrics for one concept (single-concept entry)."""
    codes = constituents(concept)
    if not codes:
        return pd.DataFrame()
    amt_panel = load_panel(codes, field="total_turnover").sort_index()
    return _concept_metrics(amt_panel, market_amt, top_n)


def crowding_latest_per_concept(
    *, top_n: int = 5,
    concepts: Iterable[str] | None = None,
    universe_amt_panel: pd.DataFrame | None = None,
    market_amt: pd.Series | None = None,
    sector_panel: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Latest crowding snapshot for each concept.

    Optimisation: build a universe-wide `total_turnover` panel ONCE and slice
    columns per concept, instead of re-loading per-concept panels (which is
    O(N_concepts × N_codes) parquet reads — each cached via load_stock, but
    still rebuilding the wide DataFrame each time is wasteful).

    Pre-loaded params (all optional) let the Streamlit layer pass cached panels
    to avoid recomputing them across modules.
    """
    theme_lookup = {c: theme for theme, items in HOT_CONCEPTS.items() for c in items}
    selected = list(concepts) if concepts is not None else (
        [c for items in HOT_CONCEPTS.values() for c in items]
    )

    if market_amt is None:
        full_a = load_full_a()
        if full_a.empty:
            return pd.DataFrame()
        market_amt = full_a.set_index("date")["amt"]

    if sector_panel is None:
        sector_panel = sector_close_panel()
    rets5 = n_day_return(sector_panel, 5) if not sector_panel.empty else pd.DataFrame()

    # Build universe-wide amount panel once
    if universe_amt_panel is None:
        all_codes = sorted({c for concept in selected for c in constituents(concept)})
        universe_amt_panel = load_panel(all_codes, field="total_turnover").sort_index()

    rows: list[dict] = []
    for concept in selected:
        concept_codes = [c for c in constituents(concept) if c in universe_amt_panel.columns]
        if not concept_codes:
            rows.append({
                "theme": theme_lookup.get(concept),
                "concept": concept,
                "top_n_amount_yi": float("nan"),
                "share_pct": float("nan"),
                "strength_pct": float("nan"),
                "peak_share_60d": float("nan"),
                "decay_pct": float("nan"),
                "days_in_top7": 0,
            })
            continue
        amt_panel = universe_amt_panel[concept_codes]
        hist = _concept_metrics(amt_panel, market_amt, top_n)
        if hist.empty:
            continue
        last = hist.iloc[-1]
        rows.append({
            "theme": theme_lookup.get(concept),
            "concept": concept,
            "top_n_amount_yi": round(float(last["top_n_amount"]) / 1e8, 2),
            "share_pct": round(float(last["share_pct"]), 3),
            "strength_pct": round(float(last["strength_pct"]), 1),
            "peak_share_60d": round(float(last["peak_share_60d"]), 3),
            "decay_pct": round(float(last["decay_pct"]), 1),
            "days_in_top7": _days_in_top7(rets5, concept, k=7),
        })
    df = pd.DataFrame(rows)
    return df.sort_values("share_pct", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Market-level crowding state
# ---------------------------------------------------------------------------

def market_crowding_state(
    crowding_df: pd.DataFrame | None = None,
    *,
    abs_share_threshold_pct: float = 8.0,
) -> dict:
    """Aggregate concept crowding → market-level state.

    abs_crowding: top theme share > `abs_share_threshold_pct` (default 8%
    of the whole-market amount). This is a heuristic — calibrate with
    historical 绝对抱团 episodes once backtesting is in place.
    """
    df = crowding_df if crowding_df is not None else crowding_latest_per_concept()
    if df.empty:
        return {}
    df_valid = df.dropna(subset=["share_pct"])
    if df_valid.empty:
        return {}
    top = df_valid.iloc[0]
    top2_share = float(df_valid.head(2)["share_pct"].sum())
    return {
        "top_theme": top["concept"],
        "top_theme_share_pct": float(top["share_pct"]),
        "top_theme_days_in_top7": int(top["days_in_top7"]),
        "top_theme_decay_pct": float(top["decay_pct"]) if not pd.isna(top["decay_pct"]) else None,
        "top2_concentration_pct": round(top2_share, 3),
        "abs_crowding": bool(top["share_pct"] >= abs_share_threshold_pct),
        "abs_share_threshold_pct": abs_share_threshold_pct,
    }


# ---------------------------------------------------------------------------
# Per-stock capacity focus
# ---------------------------------------------------------------------------

def stock_capacity_focus(stock_code: str, *,
                          top_n_within_theme: int = 3,
                          require_top7: bool = True) -> dict | None:
    """Return capacity-focus state for one stock.

    A stock is a "容量焦点" when:
      - its amount rank within at least one of its concepts is ≤ top_n_within_theme
      - that concept is in 5-day-return Top7 (if require_top7)

    Returns dict with the strongest matching concept's metadata, or None.
    """
    from .codes import wind_to_rq
    from .tags import _amount_rank_in_theme, _theme_snapshot, stock_themes

    rq = stock_code if ".XSH" in stock_code.upper() else wind_to_rq(stock_code)
    themes = stock_themes(rq)
    if not themes:
        return None

    theme_snap = _theme_snapshot()
    matches: list[dict] = []
    for t in themes:
        rank = _amount_rank_in_theme(rq, t["concept"])
        if rank is None or rank > top_n_within_theme:
            continue
        state = theme_snap.get(t["concept"], {})
        in_top7 = state.get("in_top7", False)
        if require_top7 and not in_top7:
            continue
        matches.append({
            "concept": t["concept"],
            "theme": t["theme"],
            "amount_rank": rank,
            "in_top7": in_top7,
            "top7_rank": state.get("top7_rank"),
            "sc30": state.get("sc30"),
        })
    if not matches:
        return None
    # Pick the best: lowest amount_rank, then in_top7 lowest rank
    matches.sort(key=lambda m: (m["amount_rank"],
                                  m["top7_rank"] if m["top7_rank"] is not None else 99))
    return matches[0]
