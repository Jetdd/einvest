"""Overlay live quant data onto industry-chain segments.

For each segment we equal-weight its constituent companies to get a segment-level
return / breadth, so the chain can be colored by "where the money is today".
"""
from __future__ import annotations

import pandas as pd

from ..io import load_stock, stock_name
from .chain import load_chain


def _company_metrics(rq_code: str) -> dict | None:
    """Latest close / 1d / 5d pct / above-MA5 for one stock."""
    df = load_stock(rq_code)
    if df.empty or len(df) < 2:
        return None
    close = df["close"]
    last = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    ret_1d = (last / prev - 1) * 100 if prev else 0.0
    ret_5d = (last / float(close.iloc[-6]) - 1) * 100 if len(close) > 5 else float("nan")
    ma5 = float(close.rolling(5).mean().iloc[-1]) if len(close) >= 5 else float("nan")
    return {
        "close": round(last, 2),
        "ret_1d": round(ret_1d, 2),
        "ret_5d": round(ret_5d, 2) if not pd.isna(ret_5d) else None,
        "above_ma5": (not pd.isna(ma5)) and last > ma5,
    }


def segment_strength(companies_parsed: list[tuple[str, str]]) -> dict:
    """Equal-weight segment metrics over its companies."""
    rows = []
    for name, rq in companies_parsed:
        m = _company_metrics(rq)
        if m is None:
            continue
        rows.append({"name": name or stock_name(rq) or rq, "code": rq, **m})
    if not rows:
        return {"n": 0, "ret_1d": None, "ret_5d": None, "above_ma5_pct": None,
                "companies": []}
    df = pd.DataFrame(rows)
    return {
        "n": len(df),
        "ret_1d": round(float(df["ret_1d"].mean()), 2),
        "ret_5d": (round(float(df["ret_5d"].dropna().mean()), 2)
                   if df["ret_5d"].notna().any() else None),
        "above_ma5_pct": round(100 * float(df["above_ma5"].mean()), 0),
        "companies": df.sort_values("ret_1d", ascending=False).to_dict("records"),
    }


def chain_with_strength(concept: str) -> dict | None:
    """load_chain(concept) with each segment annotated with `strength`."""
    data = load_chain(concept)
    if data is None:
        return None
    for tier, segments in (data.get("chain") or {}).items():
        for seg in segments or []:
            seg["strength"] = segment_strength(seg.get("companies_parsed", []))
    return data
