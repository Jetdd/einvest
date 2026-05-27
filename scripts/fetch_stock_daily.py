"""Download 5y daily OHLCV for the current Wind hot-concept universe.

Universe comes from `einvest.io.universe()`, which itself reads the dm_data
hotconcept cache. Save layout (compatible with dm_data convention):

    C:\\projects\\data_new\\stock\\1d\\{rq_code}.parquet

Uses rqdatac for efficient batched fetching. Skips files that already exist
unless --force is passed. Resumable. Skips .NEEQ codes (北证, not in rqdatac).
"""
from __future__ import annotations

import argparse
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import rqdatac as rq
from joblib import Parallel, delayed

from einvest.config import DEFAULT_START, RQ_PASSWORD, RQ_USER, STOCK_DIR
from einvest.io import universe


BATCH_SIZE = 30
N_JOBS = 4


def _ensure_init() -> None:
    if not rq.initialized():
        rq.init(RQ_USER, RQ_PASSWORD)


def _download_batch(codes: list[str], start: str, end: str, out_dir: Path,
                    force: bool) -> tuple[int, int]:
    _ensure_init()
    todo = [c for c in codes if force or not (out_dir / f"{c}.parquet").exists()]
    if not todo:
        return 0, len(codes)
    df = rq.get_price(todo, start_date=start, end_date=end,
                      frequency="1d", fields=None, adjust_type="pre")
    if df is None or len(df) == 0:
        return 0, len(codes)
    if isinstance(df.index, pd.MultiIndex):
        saved = 0
        for code, sub in df.groupby(level=0):
            sub.reset_index().to_parquet(out_dir / f"{code}.parquet", index=False)
            saved += 1
        return saved, len(codes)
    df.reset_index().to_parquet(out_dir / f"{todo[0]}.parquet", index=False)
    return 1, len(codes)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--start", default=DEFAULT_START)
    p.add_argument("--end", default=pd.Timestamp.today().strftime("%Y%m%d"))
    p.add_argument("--force", action="store_true",
                   help="Re-download even if file exists")
    p.add_argument("--n-jobs", type=int, default=N_JOBS)
    args = p.parse_args()

    STOCK_DIR.mkdir(parents=True, exist_ok=True)

    warnings.filterwarnings("ignore")
    full = universe()
    neeq = [c for c in full if c.endswith(".NEEQ")]
    universe_list = [c for c in full if not c.endswith(".NEEQ")]
    print(f"Wind universe: {len(full)}   北证 (.NEEQ, skipped): {len(neeq)}   "
          f"rqdatac-able: {len(universe_list)}   range: {args.start} → {args.end}")

    batches = [universe_list[i: i + BATCH_SIZE]
               for i in range(0, len(universe_list), BATCH_SIZE)]
    print(f"Batches: {len(batches)} of size ≤ {BATCH_SIZE}")

    t0 = time.time()
    results = Parallel(n_jobs=args.n_jobs)(
        delayed(_download_batch)(b, args.start, args.end, STOCK_DIR, args.force)
        for b in batches
    )
    saved = sum(s for s, _ in results)
    total = sum(t for _, t in results)
    print(f"\nDone: saved {saved} (of {total}) files in {time.time() - t0:.1f}s")
    print(f"Output: {STOCK_DIR}")


if __name__ == "__main__":
    main()
