"""Local parquet IO + Wind-source universe resolution.

Stock and index price files are stored as parquet at::

    {DATA_ROOT}/stock/1d/{rq_code}.parquet      e.g. 000001.XSHE.parquet
    {DATA_ROOT}/index/1d/{code}.parquet         e.g. 000001.XSHG.parquet  /  8841388.WI.parquet

Concepts come from the Wind hotconcept cache (managed by `dm_data.concepts`).

Caching note
------------
`load_stock` / `load_index` / `constituents` are memoised via `functools.cache`
because the cross-module call graph reads them many times per dashboard refresh
(market_state, crowding, RRG, cycle, etc.). The returned DataFrames are treated
as read-only inputs by all current callers; do not mutate them in place. Call
`clear_io_cache()` to invalidate (e.g. after a fresh daily data pull).
"""
from __future__ import annotations

import functools
from typing import Iterable

import pandas as pd

from dm_data import get_concept_constituents, load_stock_hotconcept, wind

from .codes import rq_to_wind, wind_to_rq
from .config import INDEX_DIR, STOCK_DIR
from .sectors import FULL_A_WIND, HOT_CONCEPTS


# ---------------------------------------------------------------------------
# Local parquet readers — cached (treat results as read-only)
# ---------------------------------------------------------------------------

@functools.cache
def load_stock(code: str) -> pd.DataFrame:
    """Daily OHLCV for one rq-format stock code. Empty if missing.

    Cached: ~150 KB per file, ~1500 stocks ⇒ ~250 MB resident memory upper bound.
    """
    p = STOCK_DIR / f"{code}.parquet"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


@functools.cache
def load_index(code: str) -> pd.DataFrame:
    p = INDEX_DIR / f"{code}.parquet"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def clear_io_cache() -> None:
    """Drop all cached parquet frames. Call after a daily data refresh."""
    load_stock.cache_clear()
    load_index.cache_clear()
    constituents.cache_clear()
    _stock_name_map.cache_clear()


def load_close_panel(codes: Iterable[str]) -> pd.DataFrame:
    """Wide panel indexed by date, columns = rq_code, values = close."""
    pieces: dict[str, pd.Series] = {}
    for c in codes:
        df = load_stock(c)
        if df.empty:
            continue
        pieces[c] = df.set_index("date")["close"]
    if not pieces:
        return pd.DataFrame()
    return pd.DataFrame(pieces).sort_index()


def load_panel(codes: Iterable[str], field: str = "close") -> pd.DataFrame:
    pieces: dict[str, pd.Series] = {}
    for c in codes:
        df = load_stock(c)
        if df.empty or field not in df.columns:
            continue
        pieces[c] = df.set_index("date")[field]
    if not pieces:
        return pd.DataFrame()
    return pd.DataFrame(pieces).sort_index()


# ---------------------------------------------------------------------------
# Universe — from dm_data Wind hotconcept cache
# ---------------------------------------------------------------------------

@functools.cache
def _constituents_cached(concept: str, exact: bool, as_rq: bool) -> tuple[str, ...]:
    wind_codes = get_concept_constituents(concept, exact=exact, as_list=True)
    return tuple(wind_to_rq(c) for c in wind_codes) if as_rq else tuple(wind_codes)


def constituents(concept: str, *, exact: bool = True, as_rq: bool = True) -> list[str]:
    """Constituents of one Wind concept. By default returns rqdatac-format codes.

    Cached on (concept, exact, as_rq). Returns a fresh list each call so callers
    can mutate the list without affecting the cache (the underlying tuple is
    immutable).
    """
    return list(_constituents_cached(concept, exact, as_rq))


# Attach `cache_clear` to `constituents` for parity with the @functools.cache
# decorated functions above (clear_io_cache calls it).
constituents.cache_clear = _constituents_cached.cache_clear  # type: ignore[attr-defined]


def universe(concepts: Iterable[str] | None = None) -> list[str]:
    """Union of constituents across the chosen Wind concepts (rq format)."""
    from .sectors import all_concepts as _all
    selected = list(concepts) if concepts is not None else _all()
    out: set[str] = set()
    for c in selected:
        for code in constituents(c):
            out.add(code)
    return sorted(out)


def mapping_long() -> pd.DataFrame:
    """Long DataFrame: theme, concept, wind_code, rq_code."""
    rows: list[dict] = []
    for theme, concepts in HOT_CONCEPTS.items():
        for concept in concepts:
            for wc in get_concept_constituents(concept, exact=True, as_list=True):
                rows.append({"theme": theme, "concept": concept,
                             "wind_code": wc, "rq_code": wind_to_rq(wc)})
    return pd.DataFrame(rows)


def latest_concept_date() -> str | None:
    df = load_stock_hotconcept()
    if df.empty:
        return None
    return str(df["trade_date"].max())


@functools.cache
def _stock_name_map() -> dict[str, str]:
    df = load_stock_hotconcept()
    if df.empty or "wind_code" not in df.columns or "stock_name" not in df.columns:
        return {}
    latest = df
    if "trade_date" in latest.columns:
        latest = latest[latest["trade_date"] == latest["trade_date"].max()]
    names = latest.dropna(subset=["wind_code"]).drop_duplicates("wind_code")
    return {
        str(row["wind_code"]).upper(): str(row["stock_name"])
        for _, row in names.iterrows()
        if not pd.isna(row.get("stock_name")) and str(row["stock_name"]).strip()
    }


def stock_name(code: str) -> str | None:
    """Return stock short name from the local Wind hotconcept cache."""
    wind_code = rq_to_wind(code.strip().upper())
    return _stock_name_map().get(wind_code)


# ---------------------------------------------------------------------------
# 万得全A (8841388.WI) — fetch / load
# ---------------------------------------------------------------------------

_FULL_A_PATH = INDEX_DIR / f"{FULL_A_WIND}.parquet"


def fetch_full_a(start_date: str = "2020-01-01",
                 end_date: str | None = None,
                 save: bool = True) -> pd.DataFrame:
    """Pull 万得全A daily aggregate (close/amt/low/high/open) from Wind."""
    wind.start()
    if end_date is None:
        end_date = pd.Timestamp.today().strftime("%Y-%m-%d")
    df = wind.wsd(FULL_A_WIND, "close,amt,low,high,open", start_date, end_date, "unit=1")
    df = df.reset_index().rename(columns={
        "index": "date",
        "CLOSE": "close", "AMT": "amt", "LOW": "low", "HIGH": "high", "OPEN": "open",
    })
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    if save:
        _FULL_A_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(_FULL_A_PATH, index=False)
    return df


def load_full_a() -> pd.DataFrame:
    if not _FULL_A_PATH.exists():
        return fetch_full_a()
    df = pd.read_parquet(_FULL_A_PATH)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)
