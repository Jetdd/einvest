"""One-shot daily data refresh for einvest.

Steps:
  1. fetch Wind hotconcepts for today
  2. fetch 万得全A via Wind wsd
  3. fetch main indices via rqdatac
  4. smart-append missing rows to existing stock parquets (rqdatac)
  5. build sector_feature_daily.parquet
  6. build market_state_daily.parquet
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

import pandas as pd
import rqdatac as rq

from einvest.config import (
    DEFAULT_START, INDEX_DIR, RQ_PASSWORD, RQ_USER, STOCK_DIR,
    MARKET_STATE_DAILY, SECTOR_FEATURE_DAILY, FEATURE_DIR, FULL_A_UNIVERSE,
)
from einvest.sectors import ALL_INDICES
from einvest.io import fetch_full_a

from dm_data import wind
from dm_data.concepts import save_stock_hotconcept


BATCH_SIZE = 50
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")
TODAY_RQ = pd.Timestamp.today().strftime("%Y%m%d")


# ---------------------------------------------------------------------------
# Step 1 — Wind hotconcepts
# ---------------------------------------------------------------------------

def step_hotconcepts() -> None:
    print(f"\n[1/6] Wind hotconcepts → {TODAY}")
    wind.start()
    t0 = time.time()
    codes = wind.get_all_a_codes(TODAY)
    print(f"  A-share codes: {len(codes)}  ({time.time()-t0:.1f}s)")
    t0 = time.time()
    df = wind.get_hot_concepts(codes, trade_date=TODAY, batch_size=200)
    print(f"  rows={len(df)}  concepts={df['concept'].nunique()}  ({time.time()-t0:.1f}s)")
    path = save_stock_hotconcept(df)
    print(f"  saved → {path}")


# ---------------------------------------------------------------------------
# Step 2 — 万得全A (8841388.WI) via Wind wsd
# ---------------------------------------------------------------------------

def step_full_a() -> None:
    from einvest.sectors import FULL_A_WIND
    print(f"\n[2/6] 万得全A ({FULL_A_WIND})")
    df = fetch_full_a(end_date=TODAY, save=True)
    print(f"  rows={len(df)}  last={df['date'].max().date()}")


# ---------------------------------------------------------------------------
# Step 3 — Main indices via rqdatac
# ---------------------------------------------------------------------------

def step_indices() -> None:
    print(f"\n[3/6] Main indices (rqdatac)")
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    for name, code in ALL_INDICES.items():
        df = rq.get_price(
            order_book_ids=code,
            start_date=DEFAULT_START,
            end_date=TODAY_RQ,
            frequency="1d",
            adjust_type="none",
        )
        if df is None or len(df) == 0:
            print(f"  [empty] {name} {code}")
            continue
        if isinstance(df.index, pd.MultiIndex):
            df = df.droplevel(0)
        df = df.reset_index()
        df.to_parquet(INDEX_DIR / f"{code}.parquet", index=False)
        print(f"  [ok] {name:<8} {code:<14} rows={len(df):>5}")


# ---------------------------------------------------------------------------
# Step 4 — Smart-append missing stock rows
# ---------------------------------------------------------------------------

def _last_date(path: Path) -> pd.Timestamp | None:
    try:
        df = pd.read_parquet(path, columns=["date"])
        return pd.to_datetime(df["date"]).max()
    except Exception:
        return None


def step_stocks() -> None:
    print(f"\n[4/6] Stock daily smart-update — full A universe")
    STOCK_DIR.mkdir(parents=True, exist_ok=True)

    # Enumerate the full live A-share universe (沪/深/科创/创业) and persist it
    # so downstream readers (breadth / MST / 涨跌停) don't need rqdatac.
    ai = rq.all_instruments(type="CS", market="cn", date=TODAY)
    codes = sorted(str(c) for c in ai["order_book_id"] if not str(c).endswith(".NEEQ"))
    FULL_A_UNIVERSE.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"order_book_id": codes}).to_parquet(FULL_A_UNIVERSE, index=False)
    print(f"  Full A universe: {len(codes)} codes  (saved → {FULL_A_UNIVERSE.name})")

    # Target = latest trading day on/before today (handles weekends/holidays so
    # we don't re-pull the whole market on every non-trading day).
    tdays = rq.get_trading_dates(
        start_date=(pd.Timestamp(TODAY_RQ) - pd.Timedelta(days=15)).strftime("%Y%m%d"),
        end_date=TODAY_RQ,
    )
    target_dt = pd.Timestamp(tdays[-1]) if tdays else pd.Timestamp(TODAY_RQ)
    print(f"  Target trading date: {target_dt.date()}")

    # A file is stale if it lacks the target trading day's bar.
    stale: list[str] = []
    missing: list[str] = []
    for code in codes:
        p = STOCK_DIR / f"{code}.parquet"
        if not p.exists():
            missing.append(code)
        else:
            last = _last_date(p)
            if last is None or last.date() < target_dt.date():
                stale.append(code)

    print(f"  Missing: {len(missing)}   Stale: {len(stale)}")

    all_to_update = missing + stale
    if not all_to_update:
        print("  All files up-to-date.")
        return

    # Fetch and merge in batches
    t0 = time.time()
    saved = 0
    for i in range(0, len(all_to_update), BATCH_SIZE):
        batch = all_to_update[i: i + BATCH_SIZE]
        try:
            df = rq.get_price(
                batch,
                start_date=DEFAULT_START,
                end_date=TODAY_RQ,
                frequency="1d",
                fields=None,
                adjust_type="pre",
            )
        except Exception as e:
            print(f"  [warn] batch {i//BATCH_SIZE} failed: {e}")
            continue
        if df is None or len(df) == 0:
            continue
        if isinstance(df.index, pd.MultiIndex):
            for code, sub in df.groupby(level=0):
                sub.reset_index().to_parquet(STOCK_DIR / f"{code}.parquet", index=False)
                saved += 1
        else:
            if batch:
                df.reset_index().to_parquet(STOCK_DIR / f"{batch[0]}.parquet", index=False)
                saved += 1
        print(f"  batch {i//BATCH_SIZE+1}/{-(-len(all_to_update)//BATCH_SIZE)}: saved {saved}", end="\r")

    print(f"\n  Done: {saved} files in {time.time()-t0:.1f}s")


# ---------------------------------------------------------------------------
# Step 5 — sector_feature_daily
# ---------------------------------------------------------------------------

def step_sector_features() -> None:
    print(f"\n[5/6] sector_feature_daily")
    from build_sector_feature_daily import build_sector_feature_daily
    path = build_sector_feature_daily()
    df = pd.read_parquet(path)
    print(f"  rows={len(df)}  last={df['trade_date'].max()}")


# ---------------------------------------------------------------------------
# Step 6 — market_state_daily
# ---------------------------------------------------------------------------

def step_market_state() -> None:
    print(f"\n[6/6] market_state_daily")
    from build_market_state_daily import build_market_state_daily
    path = build_market_state_daily()
    df = pd.read_parquet(path)
    last = df.iloc[-1]
    print(f"  rows={len(df)}  date={last['trade_date']}  phase={last.get('cycle_phase','?')}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"=== einvest daily update  {TODAY} ===")

    step_hotconcepts()

    rq.init(RQ_USER, RQ_PASSWORD)

    step_full_a()
    step_indices()
    step_stocks()

    # Clear IO caches so build steps see fresh data
    from einvest.io import clear_io_cache
    from einvest.cycle import clear_cycle_cache
    clear_io_cache()
    clear_cycle_cache()

    step_sector_features()
    step_market_state()

    print(f"\n=== Done ===")


if __name__ == "__main__":
    main()
