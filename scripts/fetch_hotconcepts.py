"""Refresh the Wind hotconcept cache for one trade date.

Saves into the dm_data cache at::

    {DM_INTRADAY_ROOT}/meta/symbols/stock_hotconcept.parquet

Existing rows for the same trade_date are replaced; older snapshots preserved.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from dm_data import wind
from dm_data.concepts import save_stock_hotconcept


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=pd.Timestamp.today().strftime("%Y-%m-%d"),
                   help="Trade date (default: today)")
    p.add_argument("--batch-size", type=int, default=200)
    args = p.parse_args()

    wind.start()

    t0 = time.time()
    codes = wind.get_all_a_codes(args.date)
    print(f"A-share codes on {args.date}: {len(codes)}   ({time.time() - t0:.1f}s)")

    t0 = time.time()
    df = wind.get_hot_concepts(codes, trade_date=args.date, batch_size=args.batch_size)
    print(f"hotconcept rows: {len(df)}  ({time.time() - t0:.1f}s)")
    print(f"unique concepts: {df['concept'].nunique()}")

    path = save_stock_hotconcept(df)
    print(f"saved → {path}")


if __name__ == "__main__":
    main()
