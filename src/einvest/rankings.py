"""Sector N-day return ranking — the 127板块 Top7 framework.

Following the einvest 公众号 article (board ranking):
    ZS_i(t) = sector_close_i(t) / sector_close_i(t-N) - 1     (N-day return)
    Top7 = the 7 largest ZS_i across sectors on date t.

We add:
- Migration tags:
    新晋    — appears in today's Top7 but not yesterday's
    连续    — in today's and yesterday's
    回归    — in today's, not yesterday's, but in 前日's
    掉出    — in yesterday's, not today's
- Top3 history: time series of which sectors held Top3 over time.

Built on Wind concepts and the equal-weighted sector_close from heatmap.py.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

from .heatmap import sector_close
from .sectors import HOT_CONCEPTS


def sector_close_panel(concepts: Iterable[str] | None = None) -> pd.DataFrame:
    """Wide DataFrame of sector close series, index = date, columns = concept."""
    selected = list(concepts) if concepts is not None else (
        [c for items in HOT_CONCEPTS.values() for c in items]
    )
    out: dict[str, pd.Series] = {}
    for concept in selected:
        s = sector_close(concept)
        if not s.empty:
            out[concept] = s
    if not out:
        return pd.DataFrame()
    return pd.DataFrame(out).sort_index()


def n_day_return(panel: pd.DataFrame, n: int) -> pd.DataFrame:
    """Return panel of N-day pct change. Multiply by 100 → percent."""
    return panel.pct_change(n) * 100.0


def top_k_per_date(returns: pd.DataFrame, k: int = 7) -> pd.DataFrame:
    """Long DataFrame: date, rank (1..k), concept, ret_pct."""
    rows: list[dict] = []
    for date, row in returns.iterrows():
        ranked = row.dropna().sort_values(ascending=False).head(k)
        for i, (concept, val) in enumerate(ranked.items(), start=1):
            rows.append({"date": date, "rank": i, "concept": concept, "ret_pct": float(val)})
    return pd.DataFrame(rows)


def latest_topk_migration(returns: pd.DataFrame, k: int = 7) -> pd.DataFrame:
    """Compare today / yesterday / 前日 Top-k and tag migration.

    Returns columns: concept, rank_today, rank_yest, rank_d2, tag, ret_pct
    tag ∈ {新晋, 连续, 回归, 掉出}.
    """
    if returns.empty or len(returns) < 3:
        return pd.DataFrame()
    last = returns.iloc[-1].dropna().sort_values(ascending=False).head(k)
    yest = returns.iloc[-2].dropna().sort_values(ascending=False).head(k)
    d2 = returns.iloc[-3].dropna().sort_values(ascending=False).head(k)

    last_set = set(last.index)
    yest_set = set(yest.index)
    d2_set = set(d2.index)
    union = last_set | yest_set
    last_rank = {c: i + 1 for i, c in enumerate(last.index)}
    yest_rank = {c: i + 1 for i, c in enumerate(yest.index)}
    d2_rank = {c: i + 1 for i, c in enumerate(d2.index)}

    rows: list[dict] = []
    for concept in union:
        in_now = concept in last_set
        in_yest = concept in yest_set
        in_d2 = concept in d2_set
        if in_now and in_yest:
            tag = "连续"
        elif in_now and not in_yest and in_d2:
            tag = "回归"
        elif in_now and not in_yest:
            tag = "新晋"
        elif not in_now and in_yest:
            tag = "掉出"
        else:
            tag = "—"
        rows.append({
            "concept": concept,
            "rank_today": last_rank.get(concept),
            "rank_yest":  yest_rank.get(concept),
            "rank_d2":    d2_rank.get(concept),
            "tag": tag,
            "ret_pct_today": float(returns.iloc[-1].get(concept, float("nan"))),
        })
    df = pd.DataFrame(rows)
    rank_cols = ["rank_today", "rank_yest", "rank_d2"]
    df[rank_cols] = df[rank_cols].astype("Int64")
    # sort: in-now first by rank_today asc, then 掉出 at bottom
    df["sort_key"] = df["rank_today"].fillna(99)
    df = df.sort_values(["sort_key", "tag"]).drop(columns="sort_key").reset_index(drop=True)
    return df


def topk_persistence(returns: pd.DataFrame, k: int = 7, window: int = 20) -> pd.DataFrame:
    """For each concept, # of days it was in Top-k over the last `window` days."""
    if returns.empty:
        return pd.DataFrame()
    recent = returns.tail(window)
    counts: dict[str, int] = {}
    for _, row in recent.iterrows():
        for c in row.dropna().sort_values(ascending=False).head(k).index:
            counts[c] = counts.get(c, 0) + 1
    return pd.Series(counts, name=f"days_in_top{k}_last{window}").sort_values(ascending=False).to_frame()
