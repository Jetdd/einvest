"""einvest 盘后快照 — Wind 概念 + 万得全A 单口径，第一档完整版。

Sections:
  1. CCI (主指数 4 个)
  2. 流动性 (Wind 万得全A AMT)
  3. 市场广度 — MST_5/13/50 + 涨跌家数 + 涨跌停家数 + breadth_ratio
  4. 板块热力图 Top
  5. 板块 Top7 N日涨幅排名 + 迁移
  6. 板块周期详情表 (SC30/SC3/SC60/heat/ret_5d/phase)
"""
from __future__ import annotations

import pandas as pd

from .config import STOCK_DIR
from .cycle import cycle_detail_latest
from .heatmap import heatmap_latest
from .indicators import (
    cci,
    classify_cci,
    limit_count,
    liquidity_band,
    liquidity_score,
    mst,
    up_down_count,
)
from .io import full_a_universe, load_close_panel, load_full_a, load_index
from .rankings import latest_topk_migration, n_day_return, sector_close_panel
from .sectors import FULL_A_WIND, MAIN_INDICES


# ---------------------------------------------------------------------------
# Section snapshots
# ---------------------------------------------------------------------------

def cci_snapshot() -> pd.DataFrame:
    rows: list[dict] = []
    for name, code in MAIN_INDICES.items():
        df = load_index(code)
        if df.empty:
            continue
        cci14 = cci(df, 14)
        cci84 = cci(df, 84)
        rows.append({
            "name": name,
            "code": code,
            "date": df["date"].iloc[-1].date(),
            "close": round(float(df["close"].iloc[-1]), 2),
            "cci14": round(float(cci14.iloc[-1]), 1),
            "cci14_state": classify_cci(cci14.iloc[-1]),
            "cci84": round(float(cci84.iloc[-1]), 1),
            "cci84_state": classify_cci(cci84.iloc[-1]),
        })
    return pd.DataFrame(rows)


def liquidity_snapshot(window: int = 252) -> dict:
    df = load_full_a()
    if df.empty:
        return {}
    amt = df.set_index("date")["amt"]
    score = liquidity_score(amt, window=window).iloc[-1]
    return {
        "date": df["date"].iloc[-1].date(),
        "total_amount_yuan": float(amt.iloc[-1]),
        "total_amount_billion": round(float(amt.iloc[-1]) / 1e8, 2),  # 亿元
        "score": round(float(score), 1) if not pd.isna(score) else None,
        "band": liquidity_band(score),
        "source": f"Wind {FULL_A_WIND}",
    }


def breadth_snapshot(close_panel: pd.DataFrame, codes: list[str]) -> dict:
    """Combine MST, up/down count, limit count into one snapshot row."""
    if close_panel.empty:
        return {}
    bdf = mst(close_panel, windows=(5, 13, 50))
    udc = up_down_count(close_panel)
    lc = limit_count(STOCK_DIR, codes)

    last_date = bdf.index[-1]
    out = {
        "date": last_date.date(),
        "n_stocks": len(codes),
        "MST_5": round(float(bdf.loc[last_date, "MST_5"]), 1),
        "MST_13": round(float(bdf.loc[last_date, "MST_13"]), 1),
        "MST_50": round(float(bdf.loc[last_date, "MST_50"]), 1),
        "up_count": int(udc.loc[last_date, "up_count"]),
        "down_count": int(udc.loc[last_date, "down_count"]),
        "flat_count": int(udc.loc[last_date, "flat_count"]),
        "breadth_ratio": round(float(udc.loc[last_date, "breadth_ratio"]), 2),
    }
    if not lc.empty and last_date in lc.index:
        out["limit_up_count"] = int(lc.loc[last_date, "limit_up_count"])
        out["limit_down_count"] = int(lc.loc[last_date, "limit_down_count"])
    else:
        out["limit_up_count"] = None
        out["limit_down_count"] = None
    return out


def topk_snapshot(n_days: int = 5, k: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Top-k by N-day return today + migration vs prior 2 sessions.

    Returns (top_today_df, migration_df).
    """
    panel = sector_close_panel()
    if panel.empty:
        return pd.DataFrame(), pd.DataFrame()
    rets = n_day_return(panel, n_days)
    last = rets.iloc[-1].dropna().sort_values(ascending=False).head(k)
    top_df = pd.DataFrame({
        "rank": range(1, len(last) + 1),
        "concept": last.index,
        f"ret_{n_days}d_pct": last.values.round(2),
    })
    mig = latest_topk_migration(rets, k=k)
    return top_df, mig


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render() -> None:
    print("=" * 90)
    print(" einvest 盘后快照 — Wind 口径，第一档全量 ".center(88, "="))
    print("=" * 90)

    # 1. CCI
    print("\n[1. CCI — 指数顶底]")
    print(cci_snapshot().to_string(index=False))

    # 2. 流动性
    print("\n[2. 流动性 — 万得全A AMT]")
    liq = liquidity_snapshot()
    if liq:
        print(f"  日期：{liq['date']}")
        print(f"  总成交额：{liq['total_amount_billion']:.2f} 亿  ({liq['source']})")
        print(f"  评分：{liq['score']}   →   {liq['band']}")

    # 3. 市场广度 (一次性 load close panel，共享给 MST / up_down / limit_count)
    print("\n[3. 市场广度 — 全 A 股]")
    codes = full_a_universe()
    close_panel = load_close_panel(codes)
    bs = breadth_snapshot(close_panel, codes)
    if bs:
        print(f"  日期 {bs['date']}  样本 {bs['n_stocks']} 票")
        print(f"  MST_5={bs['MST_5']}   MST_13={bs['MST_13']}   MST_50={bs['MST_50']}")
        print(f"  涨/跌/平 = {bs['up_count']} / {bs['down_count']} / {bs['flat_count']}   "
              f"breadth_ratio = {bs['breadth_ratio']}")
        lu = bs['limit_up_count']
        ld = bs['limit_down_count']
        print(f"  涨停 {lu}   跌停 {ld}")

    # 4. 板块热力图 Top 15
    print("\n[4. 板块热力图 Top 15]")
    h = heatmap_latest()
    keep = ["theme", "concept", "heat", "delta", "arrow", "band", "n_stocks"]
    h_top = h[keep].head(15).copy()
    h_top["heat"] = h_top["heat"].round(1)
    h_top["delta"] = h_top["delta"].round(2)
    print(h_top.to_string(index=False))

    # 5. Top7 N日涨幅 + 迁移
    print("\n[5. 板块 Top7 5日涨幅排名 + 迁移]")
    top_today, mig = topk_snapshot(n_days=5, k=7)
    if not top_today.empty:
        print(top_today.to_string(index=False))
        print()
        print("  迁移（今日∪昨日 Top7）：")
        print("  " + mig.to_string(index=False).replace("\n", "\n  "))

    # 6. 板块周期详情
    print("\n[6. 板块周期详情 (按 SC30 排序)]")
    cyc = cycle_detail_latest()
    cyc_show = cyc[["theme", "concept", "n_stocks", "SC30", "SC3", "SC60",
                    "heat", "ret_5d", "ret_20d", "strength", "phase"]]
    print(cyc_show.head(20).to_string(index=False))
    print()
    print(f"  共 {len(cyc)} 个板块，按强度分档：")
    print("  " + cyc["strength"].value_counts().to_string().replace("\n", "  "))
    print("  按周期阶段：")
    print("  " + cyc["phase"].value_counts().to_string().replace("\n", "  "))

    print("\n" + "=" * 90)


if __name__ == "__main__":
    render()
