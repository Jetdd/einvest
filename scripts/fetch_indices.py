"""Download main A-share indices for CCI / market level.

Save layout:
    C:\\projects\\data_new\\index\\1d\\{code}.parquet
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import rqdatac as rq

from einvest.config import RQ_USER, RQ_PASSWORD, INDEX_DIR, DEFAULT_START
from einvest.sectors import ALL_INDICES


def main() -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    rq.init(RQ_USER, RQ_PASSWORD)
    end = pd.Timestamp.today().strftime("%Y%m%d")

    for name, code in ALL_INDICES.items():
        df = rq.get_price(
            order_book_ids=code,
            start_date=DEFAULT_START,
            end_date=end,
            frequency="1d",
            adjust_type="none",
        )
        if df is None or len(df) == 0:
            print(f"[empty] {name} {code}")
            continue
        if isinstance(df.index, pd.MultiIndex):
            df = df.droplevel(0)
        df = df.reset_index()
        out = INDEX_DIR / f"{code}.parquet"
        df.to_parquet(out, index=False)
        print(f"[ok]   {name:<8} {code:<14} rows={len(df):>5}  →  {out.name}")


if __name__ == "__main__":
    main()
