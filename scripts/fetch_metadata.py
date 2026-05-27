"""Fetch supporting metadata for the einvest universe.

Outputs (all under DATA_ROOT / "meta" / "panels" or "symbols"):

  panels/market_cap.parquet            wide: date × code, A-share circulating market cap (yuan)
  panels/free_float_cap.parquet        wide: date × code, free-float market cap (market_cap_2)
  panels/is_st.parquet                 wide: date × code, bool
  panels/is_suspended.parquet          wide: date × code, bool
  symbols/instruments.parquet          long: order_book_id, symbol, listed_date, status
  symbols/industry_sw_l1.parquet       long: order_book_id, sw_l1_code, sw_l1_name

Universe = einvest.io.universe() ∩ existing parquet files (skips .NEEQ).
"""
from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import rqdatac as rq

from einvest.config import DATA_ROOT, DEFAULT_START, RQ_PASSWORD, RQ_USER, STOCK_DIR
from einvest.io import universe


META_PANELS = DATA_ROOT / "meta" / "panels"
META_SYMBOLS = DATA_ROOT / "meta" / "symbols"
BATCH = 200


def _init() -> None:
    if not rq.initialized():
        rq.init(RQ_USER, RQ_PASSWORD)


def _factor_panel(codes: list[str], factor: str, start: str, end: str) -> pd.DataFrame:
    """Batched rqdatac.get_factor; returns a wide DataFrame (date × code)."""
    frames: list[pd.DataFrame] = []
    for i in range(0, len(codes), BATCH):
        batch = codes[i: i + BATCH]
        df = rq.get_factor(batch, factor, start, end)
        if df is None or len(df) == 0:
            continue
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    long_df = pd.concat(frames)
    # long → wide
    wide = long_df.reset_index().pivot(index="date", columns="order_book_id", values=factor)
    wide.index = pd.to_datetime(wide.index)
    return wide.sort_index()


def _bool_panel(fn, codes: list[str], start: str, end: str) -> pd.DataFrame:
    """Batched is_st_stock / is_suspended; both already return date×code."""
    frames: list[pd.DataFrame] = []
    for i in range(0, len(codes), BATCH):
        batch = codes[i: i + BATCH]
        df = fn(batch, start, end)
        if df is None or len(df) == 0:
            continue
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    wide = pd.concat(frames, axis=1)
    wide.index = pd.to_datetime(wide.index)
    return wide.sort_index()


def main() -> None:
    warnings.filterwarnings("ignore")
    _init()

    META_PANELS.mkdir(parents=True, exist_ok=True)
    META_SYMBOLS.mkdir(parents=True, exist_ok=True)

    end = pd.Timestamp.today().strftime("%Y%m%d")
    full = universe()
    universe_list = [c for c in full if not c.endswith(".NEEQ")
                     and (STOCK_DIR / f"{c}.parquet").exists()]
    print(f"universe: {len(full)}   downloadable+local: {len(universe_list)}   "
          f"range: {DEFAULT_START} → {end}")

    # -------- market caps --------
    for factor, fname in [
        ("a_share_market_val_in_circulation", "market_cap.parquet"),
        ("market_cap_2", "free_float_cap.parquet"),
    ]:
        t0 = time.time()
        wide = _factor_panel(universe_list, factor, DEFAULT_START, end)
        out = META_PANELS / fname
        wide.to_parquet(out)
        print(f"[ok] {factor}: shape={wide.shape}  → {out.name}  ({time.time()-t0:.1f}s)")

    # -------- ST / suspended --------
    for fn, fname in [
        (rq.is_st_stock, "is_st.parquet"),
        (rq.is_suspended, "is_suspended.parquet"),
    ]:
        t0 = time.time()
        wide = _bool_panel(fn, universe_list, DEFAULT_START, end)
        out = META_PANELS / fname
        wide.to_parquet(out)
        print(f"[ok] {fn.__name__}: shape={wide.shape}  → {out.name}  ({time.time()-t0:.1f}s)")

    # -------- instruments (listed_date / name / board) --------
    t0 = time.time()
    inst_objs = rq.instruments(universe_list)
    rows = [{
        "order_book_id": getattr(i, "order_book_id", None),
        "symbol": getattr(i, "symbol", None),
        "listed_date": getattr(i, "listed_date", None),
        "status": getattr(i, "status", None),
        "exchange": getattr(i, "exchange", None),
        "board_type": getattr(i, "board_type", None),
    } for i in inst_objs]
    inst_df = pd.DataFrame(rows)
    inst_df["listed_date"] = pd.to_datetime(inst_df["listed_date"], errors="coerce")
    inst_df.to_parquet(META_SYMBOLS / "instruments.parquet", index=False)
    print(f"[ok] instruments: rows={len(inst_df)}  → instruments.parquet  ({time.time()-t0:.1f}s)")

    # -------- 申万一级行业 (latest snapshot) --------
    t0 = time.time()
    sw = rq.shenwan_instrument_industry(universe_list, level=1)
    sw = sw.reset_index().rename(columns={
        "index_code": "sw_l1_code",
        "index_name": "sw_l1_name",
    })
    sw.to_parquet(META_SYMBOLS / "industry_sw_l1.parquet", index=False)
    print(f"[ok] shenwan_l1: rows={len(sw)}  industries={sw['sw_l1_name'].nunique()}  "
          f"→ industry_sw_l1.parquet  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
