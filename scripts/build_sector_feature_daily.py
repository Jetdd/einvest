"""Build sector_feature_daily snapshot from the current Wind concept universe.

Output:
    C:\projects\data_new\features\sector_feature_daily.parquet
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from einvest.config import SECTOR_FEATURE_DAILY
from einvest.cycle import cycle_detail_latest
from einvest.rankings import latest_topk_migration, n_day_return, sector_close_panel


def build_sector_feature_daily(*, replace_date: bool = True) -> Path:
    cyc = cycle_detail_latest()
    if cyc.empty:
        raise RuntimeError("No sector cycle data generated.")

    panel = sector_close_panel(cyc["concept"].dropna().tolist())
    if panel.empty:
        raise RuntimeError("No sector close panel generated.")

    trade_date = panel.index[-1].date().isoformat()
    rets = {
        1: n_day_return(panel, 1).iloc[-1],
        3: n_day_return(panel, 3).iloc[-1],
        5: n_day_return(panel, 5).iloc[-1],
        20: n_day_return(panel, 20).iloc[-1],
    }

    mig = latest_topk_migration(n_day_return(panel, 5), k=7)
    mig_map = {
        row["concept"]: row.to_dict()
        for _, row in mig.iterrows()
    } if not mig.empty else {}

    out = cyc.copy()
    out.insert(0, "trade_date", trade_date)
    out["sector_id"] = out["concept"]
    out["sector_name"] = out["concept"]
    out["sector_type"] = "wind_hotconcept"
    out["ret_1d"] = out["concept"].map(rets[1]).astype(float)
    out["ret_3d"] = out["concept"].map(rets[3]).astype(float)
    out["ret_5d_rank"] = out["concept"].map(lambda c: mig_map.get(c, {}).get("rank_today"))
    out["ret_5d_rank_yest"] = out["concept"].map(lambda c: mig_map.get(c, {}).get("rank_yest"))
    out["ret_5d_rank_d2"] = out["concept"].map(lambda c: mig_map.get(c, {}).get("rank_d2"))
    out["top7_tag"] = out["concept"].map(lambda c: mig_map.get(c, {}).get("tag"))
    out["is_top7"] = out["ret_5d_rank"].notna()
    out["source"] = "einvest.cycle_detail_latest"
    out["created_at"] = pd.Timestamp.now().isoformat(timespec="seconds")

    out = out.rename(columns={
        "concept": "concept_name",
        "SC3": "sc3",
        "SC30": "sc30",
        "SC60": "sc60",
    })

    keep = [
        "trade_date", "sector_id", "sector_name", "concept_name", "theme", "sector_type",
        "n_stocks", "close_idx", "ret_1d", "ret_3d", "ret_5d", "ret_20d",
        "sc3", "sc30", "sc60", "heat", "strength", "phase",
        "ret_5d_rank", "ret_5d_rank_yest", "ret_5d_rank_d2", "top7_tag",
        "is_top7", "source", "created_at",
    ]
    out = out[[c for c in keep if c in out.columns]]

    SECTOR_FEATURE_DAILY.parent.mkdir(parents=True, exist_ok=True)
    if replace_date and SECTOR_FEATURE_DAILY.exists():
        old = pd.read_parquet(SECTOR_FEATURE_DAILY)
        old = old[old["trade_date"].astype(str) != trade_date]
        out = pd.concat([old, out], ignore_index=True)

    out.to_parquet(SECTOR_FEATURE_DAILY, index=False)
    return SECTOR_FEATURE_DAILY


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--append", action="store_true", help="Do not replace rows for the same trade date.")
    args = parser.parse_args()

    path = build_sector_feature_daily(replace_date=not args.append)
    df = pd.read_parquet(path)
    print(f"[ok] sector_feature_daily rows={len(df)} path={path}")


if __name__ == "__main__":
    main()
