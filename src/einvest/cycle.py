"""Sector cycle detail table — one row per Wind concept with SC30/SC3/SC60/RSV
plus phase classification, replicating the PDF's 板块周期详情表 layout.
"""
from __future__ import annotations

import functools
from typing import Iterable

import pandas as pd

from .heatmap import sector_close
from .indicators.sc import sc, classify_phase, classify_strength
from .indicators.rsi import rsi_ema
from .io import constituents
from .sectors import HOT_CONCEPTS


@functools.cache
def _cycle_detail_default() -> pd.DataFrame:
    """Cached cycle detail for the default (HOT_CONCEPTS) universe."""
    return _cycle_detail_impl(None)


def cycle_detail_latest(concepts: Iterable[str] | None = None) -> pd.DataFrame:
    """Latest cycle snapshot. Default-universe call is cached; subset calls re-compute."""
    if concepts is None:
        return _cycle_detail_default()
    return _cycle_detail_impl(tuple(concepts))


def clear_cycle_cache() -> None:
    _cycle_detail_default.cache_clear()


def _cycle_detail_impl(concepts_tuple: tuple[str, ...] | None) -> pd.DataFrame:
    """Latest cycle snapshot for each concept.

    Columns:
        theme, concept, n_stocks, close_idx,
        SC3, SC30, SC60, heat (RSI+EMA5),
        ret_5d, ret_20d,
        strength (按 SC30 分档), phase (SC30+SC3 联合).
    """
    theme_lookup: dict[str, str] = {
        c: theme for theme, items in HOT_CONCEPTS.items() for c in items
    }
    selected = list(concepts_tuple) if concepts_tuple is not None else (
        [c for items in HOT_CONCEPTS.values() for c in items]
    )

    rows: list[dict] = []
    for concept in selected:
        s = sector_close(concept)
        codes = constituents(concept)
        if s.empty or len(s) < 60:
            rows.append({
                "theme": theme_lookup.get(concept),
                "concept": concept,
                "n_stocks": len(codes),
                **{k: float("nan") for k in
                   ["close_idx", "SC3", "SC30", "SC60", "heat", "ret_5d", "ret_20d"]},
                "strength": "n/a",
                "phase": "n/a",
            })
            continue

        sc_df = sc(s)
        heat = rsi_ema(s, n_rsi=14, n_ema=5)
        ret_5d = float(s.iloc[-1] / s.iloc[-6] - 1) * 100 if len(s) > 5 else float("nan")
        ret_20d = float(s.iloc[-1] / s.iloc[-21] - 1) * 100 if len(s) > 20 else float("nan")

        sc3 = float(sc_df["SC3"].iloc[-1])
        sc30 = float(sc_df["SC30"].iloc[-1])
        sc60 = float(sc_df["SC60"].iloc[-1])

        rows.append({
            "theme": theme_lookup.get(concept),
            "concept": concept,
            "n_stocks": len(codes),
            "close_idx": round(float(s.iloc[-1]), 2),
            "SC3":  round(sc3, 1),
            "SC30": round(sc30, 1),
            "SC60": round(sc60, 1),
            "heat": round(float(heat.iloc[-1]), 1) if not pd.isna(heat.iloc[-1]) else float("nan"),
            "ret_5d":  round(ret_5d, 2),
            "ret_20d": round(ret_20d, 2),
            "strength": classify_strength(sc30),
            "phase": classify_phase(sc30, sc3),
        })

    df = pd.DataFrame(rows)
    return df.sort_values("SC30", ascending=False).reset_index(drop=True)
