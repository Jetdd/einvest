"""Historical-similarity risk score (蒸馏 §4 + §5).

For each trading day we build a feature vector:
    [market_sc30, market_sc30_5d_mom, MST_5, MST_13, MST_50,
     cci84, breadth_ratio, liquidity_score]

To estimate forward risk we find the K most similar historical days
(z-scored Euclidean distance) and look at their realized 万得全A returns at
T+1 / T+5 / T+20.

Outputs:
    - win_rate at each horizon (% of similar days with positive return)
    - mean / median return at each horizon
    - top-K most similar days (for transparency)
"""
from __future__ import annotations

import functools
from dataclasses import dataclass, asdict
from typing import Any

import numpy as np
import pandas as pd

from .indicators.breadth import mst, up_down_count
from .indicators.cci import cci
from .indicators.liquidity import liquidity_score
from .indicators.sc import rsv
from .io import full_a_universe, load_close_panel, load_full_a, load_index


FEATURES = [
    "market_sc30",
    "market_sc30_5d_mom",
    "MST_5",
    "MST_13",
    "MST_50",
    "cci14",
    "cci84",
    "breadth_ratio",
    "liquidity_score",
]

HORIZONS = (1, 5, 20)


# ---------------------------------------------------------------------------
# Historical feature panel
# ---------------------------------------------------------------------------

@functools.cache
def _feature_panel(*, sh_code: str = "000001.XSHG") -> pd.DataFrame:
    """Daily feature + forward-return panel over the full available history.

    Cached because it scans the full close panel; downstream callers (Streamlit,
    KNN) can request it many times per day without re-computing.
    """
    full_a = load_full_a()
    if full_a.empty:
        return pd.DataFrame()

    full_a_dated = full_a.set_index("date").sort_index()
    close = full_a_dated["close"]
    amt = full_a_dated["amt"]
    low = full_a_dated["low"] if "low" in full_a_dated.columns else None
    high = full_a_dated["high"] if "high" in full_a_dated.columns else None

    # Market-wide SC30 (RSV30 of 万得全A, OHLC per framework primary definition)
    market_sc30 = rsv(close, 30, low=low, high=high).rename("market_sc30")
    market_sc30_5d_mom = market_sc30.diff(5).rename("market_sc30_5d_mom")

    # MST per the breadth module
    close_panel = load_close_panel(full_a_universe())
    mst_df = mst(close_panel, windows=(5, 13, 50))  # columns: MST_5/13/50

    # CCI on 上证: short (14) + long (84)
    sh = load_index(sh_code)
    if sh.empty:
        cci14 = pd.Series(name="cci14", dtype=float)
        cci84 = pd.Series(name="cci84", dtype=float)
    else:
        sh_dated = sh.set_index("date").sort_index()
        cci14 = cci(sh_dated, 14).rename("cci14")
        cci84 = cci(sh_dated, 84).rename("cci84")

    # Breadth ratio from universe close panel
    udc = up_down_count(close_panel)
    breadth_ratio = udc["breadth_ratio"].rename("breadth_ratio")

    # Liquidity score from 万得全A amount
    liq = liquidity_score(amt, 252).rename("liquidity_score")

    # Forward returns of 万得全A (in %)
    fwd = pd.DataFrame(index=close.index)
    for h in HORIZONS:
        fwd[f"ret_{h}d"] = (close.shift(-h) / close - 1) * 100

    df = pd.concat(
        [market_sc30, market_sc30_5d_mom, mst_df, cci14, cci84, breadth_ratio, liq, fwd],
        axis=1,
    )
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    # Drop rows missing any input feature (forward returns may be NaN at tail)
    df = df.dropna(subset=FEATURES)
    return df


# ---------------------------------------------------------------------------
# KNN over historical days
# ---------------------------------------------------------------------------

def _zscore_panel(df: pd.DataFrame, cols: list[str]) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Return z-scored panel + means/stds for re-using on new points."""
    mu = df[cols].mean()
    sd = df[cols].std(ddof=0).replace(0, np.nan)
    z = (df[cols] - mu) / sd
    return z, mu, sd


def find_similar_days(
    current: pd.Series,
    history: pd.DataFrame,
    *,
    top_k: int = 30,
    exclude_last_n: int = 30,
) -> pd.DataFrame:
    """Top-K most similar historical days to `current` (z-scored Euclidean).

    `current`: indexed by FEATURES; one value per feature.
    `history`: feature panel (must include FEATURES). Forward-return cols are
        kept and returned with the slice.
    `exclude_last_n`: skip the most recent N rows so we don't match the present
        on itself or near-overlapping windows.
    """
    if history.empty:
        return pd.DataFrame()

    hist = history.iloc[:-exclude_last_n] if exclude_last_n > 0 else history
    if hist.empty:
        return pd.DataFrame()

    z_hist, mu, sd = _zscore_panel(hist, FEATURES)
    z_cur = (current[FEATURES] - mu) / sd

    diff = z_hist - z_cur
    dist = np.sqrt((diff ** 2).sum(axis=1))
    top = dist.nsmallest(top_k)

    out = hist.loc[top.index].copy()
    out["distance"] = top.values
    return out.sort_values("distance")


# ---------------------------------------------------------------------------
# Risk score snapshot
# ---------------------------------------------------------------------------

@dataclass
class RiskScoreSnapshot:
    date: str
    n_similar: int
    horizons: dict[str, dict[str, float]]  # {"1d": {"win_rate": .., "mean": .., ...}, ...}
    similar_days: list[dict[str, Any]]      # top K similar days with forward returns
    current_features: dict[str, float]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _horizon_stats(rets: pd.Series) -> dict[str, float]:
    rets = rets.dropna()
    if rets.empty:
        return {"win_rate": float("nan"), "mean": float("nan"),
                "median": float("nan"), "n": 0}
    return {
        "win_rate": float((rets > 0).mean() * 100),
        "mean":     float(rets.mean()),
        "median":   float(rets.median()),
        "n":        int(len(rets)),
    }


def risk_score_snapshot(*, top_k: int = 30,
                         exclude_last_n: int = 30) -> RiskScoreSnapshot | None:
    """Compute the historical-similarity risk score for the latest day.

    Returns None if no feature history is available.
    """
    panel = _feature_panel()
    if panel.empty:
        return None

    # Current = last row that has features (forward returns may be NaN at tail)
    feat_only = panel[FEATURES].dropna()
    if feat_only.empty:
        return None
    cur_date = feat_only.index[-1]
    current = feat_only.iloc[-1]

    similar = find_similar_days(
        current, panel, top_k=top_k, exclude_last_n=exclude_last_n
    )

    horizons: dict[str, dict[str, float]] = {}
    for h in HORIZONS:
        horizons[f"{h}d"] = _horizon_stats(similar[f"ret_{h}d"])

    sim_rows: list[dict[str, Any]] = []
    for d, r in similar.head(15).iterrows():
        sim_rows.append({
            "date": d.date().isoformat(),
            "distance": round(float(r["distance"]), 3),
            "market_sc30": round(float(r["market_sc30"]), 1),
            "cci14": round(float(r["cci14"]), 1) if not pd.isna(r.get("cci14", float("nan"))) else None,
            "cci84": round(float(r["cci84"]), 1),
            "MST_5": round(float(r["MST_5"]), 1),
            "breadth_ratio": round(float(r["breadth_ratio"]), 2),
            "liquidity_score": round(float(r["liquidity_score"]), 1),
            "ret_1d":  round(float(r["ret_1d"]), 2)  if not pd.isna(r["ret_1d"])  else None,
            "ret_5d":  round(float(r["ret_5d"]), 2)  if not pd.isna(r["ret_5d"])  else None,
            "ret_20d": round(float(r["ret_20d"]), 2) if not pd.isna(r["ret_20d"]) else None,
        })

    return RiskScoreSnapshot(
        date=cur_date.date().isoformat(),
        n_similar=len(similar),
        horizons=horizons,
        similar_days=sim_rows,
        current_features={k: round(float(current[k]), 2) for k in FEATURES},
    )


def risk_light_from_stats(horizons: dict[str, dict[str, float]]) -> str:
    """Simple risk-light heuristic from KNN stats.

    红：T+5 胜率 < 40% 或 T+1 均值 < -0.5%
    绿：T+5 胜率 ≥ 60% 且 T+5 均值 > 0.5%
    黄：其它
    """
    h5 = horizons.get("5d", {})
    h1 = horizons.get("1d", {})
    win5 = h5.get("win_rate", float("nan"))
    mean5 = h5.get("mean", float("nan"))
    mean1 = h1.get("mean", float("nan"))
    if pd.isna(win5):
        return "n/a"
    if win5 < 40 or (not pd.isna(mean1) and mean1 < -0.5):
        return "红"
    if win5 >= 60 and not pd.isna(mean5) and mean5 > 0.5:
        return "绿"
    return "黄"
