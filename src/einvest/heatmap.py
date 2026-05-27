"""Sector heatmap — heat value = EMA(RSI(板块价, 14), 5) per the einvest article.

Sector price is built as the equal-weighted mean of constituents' close on each
date.

Color bands (from einvest article 1):
    <35   深绿
    35-45 绿
    45-50 亮绿
    50-55 黄
    55-65 浅红
    65-75 红
    75-85 深红
    >=85  紫红
"""
from __future__ import annotations

import functools
from typing import Iterable

import numpy as np
import pandas as pd

from .indicators.rsi import rsi_ema
from .io import constituents, load_close_panel
from .sectors import HOT_CONCEPTS


COLOR_BANDS: list[tuple[float, str]] = [
    (35, "深绿"),
    (45, "绿"),
    (50, "亮绿"),
    (55, "黄"),
    (65, "浅红"),
    (75, "红"),
    (85, "深红"),
    (np.inf, "紫红"),
]


def band(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    for threshold, label in COLOR_BANDS:
        if value < threshold:
            return label
    return "紫红"


@functools.cache
def sector_close(concept: str) -> pd.Series:
    """Equal-weighted close series for a Wind concept's constituents.

    Cached: 73 concepts × ~1500 trading days ≈ 1MB total. Cleared with
    `clear_sector_cache()` (or after a fresh daily data refresh).
    """
    codes = constituents(concept)
    if not codes:
        return pd.Series(dtype=float, name=concept)
    panel = load_close_panel(codes)
    if panel.empty:
        return pd.Series(dtype=float, name=concept)
    return panel.mean(axis=1).rename(concept)


def clear_sector_cache() -> None:
    """Drop cached sector_close series."""
    sector_close.cache_clear()


def heatmap_latest(concepts: Iterable[str] | None = None) -> pd.DataFrame:
    """Latest heat reading per concept.

    Columns: theme, concept, heat, prev_heat, delta, arrow, band, n_stocks.
    """
    theme_lookup: dict[str, str] = {
        c: theme for theme, items in HOT_CONCEPTS.items() for c in items
    }
    selected = list(concepts) if concepts is not None else (
        [c for items in HOT_CONCEPTS.values() for c in items]
    )

    rows: list[dict] = []
    for concept in selected:
        codes = constituents(concept)
        s = sector_close(concept)
        if s.empty or len(s) < 20:
            rows.append({"theme": theme_lookup.get(concept), "concept": concept,
                         "heat": float("nan"), "prev_heat": float("nan"),
                         "delta": float("nan"), "arrow": "n/a", "band": "n/a",
                         "n_stocks": len(codes)})
            continue
        heat = rsi_ema(s, n_rsi=14, n_ema=5).dropna()
        if heat.empty:
            rows.append({"theme": theme_lookup.get(concept), "concept": concept,
                         "heat": float("nan"), "prev_heat": float("nan"),
                         "delta": float("nan"), "arrow": "n/a", "band": "n/a",
                         "n_stocks": len(codes)})
            continue
        cur = float(heat.iloc[-1])
        prev = float(heat.iloc[-2]) if len(heat) > 1 else float("nan")
        delta = cur - prev if not pd.isna(prev) else float("nan")
        rows.append({
            "theme": theme_lookup.get(concept),
            "concept": concept,
            "heat": cur,
            "prev_heat": prev,
            "delta": delta,
            "arrow": "↑" if delta > 0 else ("↓" if delta < 0 else "→"),
            "band": band(cur),
            "n_stocks": len(codes),
        })
    df = pd.DataFrame(rows)
    return df.sort_values("heat", ascending=False).reset_index(drop=True)


def heatmap_history(concepts: Iterable[str] | None = None) -> pd.DataFrame:
    """Wide DataFrame of heat values, columns = concept, index = date."""
    selected = list(concepts) if concepts is not None else (
        [c for items in HOT_CONCEPTS.values() for c in items]
    )
    out: dict[str, pd.Series] = {}
    for concept in selected:
        s = sector_close(concept)
        if s.empty:
            continue
        out[concept] = rsi_ema(s, n_rsi=14, n_ema=5)
    if not out:
        return pd.DataFrame()
    return pd.DataFrame(out).sort_index()
