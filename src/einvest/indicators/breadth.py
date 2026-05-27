"""Market breadth — station-above-MA ratio (MST) and up/down/limit counts.

Three families of functions:

1. MST_N : % stocks closing above their own N-day SMA.
2. up_down_count(close_panel): daily up_count, down_count, flat_count.
3. limit_count(stock_dir, codes, dates): daily limit_up_count / limit_down_count
   (uses the limit_up / limit_down columns in the per-stock parquet files).
4. breadth_ratio: up_count / max(down_count, 1) — simple convex ratio.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Above-MA ratio (MST)
# ---------------------------------------------------------------------------

def above_ma_ratio(close_panel: pd.DataFrame, n: int) -> pd.Series:
    """% of stocks closing above their own n-day SMA, per date."""
    ma = close_panel.rolling(n, min_periods=n).mean()
    above = close_panel > ma
    valid = ma.notna()
    num = (above & valid).sum(axis=1).astype(float)
    den = valid.sum(axis=1).astype(float).replace(0.0, np.nan)
    return 100.0 * num / den


def mst(close_panel: pd.DataFrame, windows: tuple[int, ...] = (5, 13, 50)) -> pd.DataFrame:
    """Return MST_5 / MST_13 / MST_50 columns indexed by date."""
    out: dict[str, pd.Series] = {}
    for n in windows:
        out[f"MST_{n}"] = above_ma_ratio(close_panel, n)
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# Daily counts: up / down / flat
# ---------------------------------------------------------------------------

def up_down_count(close_panel: pd.DataFrame) -> pd.DataFrame:
    """Per-date up_count / down_count / flat_count using close vs previous close."""
    ret = close_panel.pct_change()
    up = (ret > 0).sum(axis=1).astype(int)
    down = (ret < 0).sum(axis=1).astype(int)
    flat = (ret == 0).sum(axis=1).astype(int)
    out = pd.DataFrame({"up_count": up, "down_count": down, "flat_count": flat})
    out["breadth_ratio"] = breadth_ratio(out["up_count"], out["down_count"])
    return out


def breadth_ratio(up: pd.Series, down: pd.Series) -> pd.Series:
    """up_count / max(down_count, 1)."""
    return up.astype(float) / down.where(down > 0, 1).astype(float)


# ---------------------------------------------------------------------------
# Limit-up / limit-down daily counts (reads per-stock parquet files)
# ---------------------------------------------------------------------------

def _is_limit(close: pd.Series, lim: pd.Series, tol: float = 1e-3) -> pd.Series:
    """A close hits the limit when close == limit (within `tol` relative)."""
    if close.empty or lim.empty:
        return pd.Series(dtype=bool)
    rel = (close - lim).abs() / lim.where(lim != 0, 1.0)
    return rel < tol


def limit_count(stock_dir: Path, codes: Iterable[str]) -> pd.DataFrame:
    """Count limit_up / limit_down occurrences per day across `codes`.

    Reads per-stock parquet files for the limit_up / limit_down / close columns.
    """
    lu_rows: list[pd.Series] = []
    ld_rows: list[pd.Series] = []
    for code in codes:
        p = stock_dir / f"{code}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p, columns=["date", "close", "limit_up", "limit_down"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        lu = _is_limit(df["close"], df["limit_up"]).rename(code)
        ld = _is_limit(df["close"], df["limit_down"]).rename(code)
        lu_rows.append(lu)
        ld_rows.append(ld)
    if not lu_rows:
        return pd.DataFrame()
    lu_panel = pd.concat(lu_rows, axis=1)
    ld_panel = pd.concat(ld_rows, axis=1)
    return pd.DataFrame({
        "limit_up_count":   lu_panel.sum(axis=1).astype(int),
        "limit_down_count": ld_panel.sum(axis=1).astype(int),
    }).sort_index()
