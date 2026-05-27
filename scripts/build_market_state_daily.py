"""Build market_state_daily from the current einvest market_state module.

Output:
    C:\\projects\\data_new\\features\\market_state_daily.parquet

The parquet stores one row per snapshot. JSON-blob columns hold the nested
position / breadth detail so the table stays flat.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from einvest.config import MARKET_STATE_DAILY
from einvest.market_state import market_state_snapshot


def _row(snap) -> dict:
    return {
        "trade_date": snap.date,
        "market_temperature": snap.market_temperature,
        "market_state": snap.market_state,
        "risk_light": snap.risk_light,
        "cycle_phase": snap.cycle_phase,
        "position_base_score": snap.position_base["score"],
        "position_flex_score": snap.position_flex["score"],
        "position_config_score": snap.position_config["score"],
        "n_strong_sectors": snap.position_config["n_strong"],
        "n_hot_sectors": snap.position_config["n_hot"],
        "n_total_sectors": snap.position_config["n_total"],
        "top_sc30": snap.breadth["top_sc30"],
        "breadth_ratio": snap.breadth["breadth_ratio"],
        "up_count": snap.breadth["up_count"],
        "down_count": snap.breadth["down_count"],
        "cci84": snap.position_flex.get("cci84"),
        "cci_state": snap.position_flex.get("cci_state"),
        "liquidity_band": snap.position_flex.get("liquidity_band"),
        "liquidity_score": snap.position_flex.get("liquidity_score"),
        "mst_5": snap.position_flex.get("mst_5"),
        "mst_13": snap.position_flex.get("mst_13"),
        "mst_50": snap.position_flex.get("mst_50"),
        "position_base_json": json.dumps(snap.position_base, ensure_ascii=False),
        "position_flex_json": json.dumps(snap.position_flex, ensure_ascii=False),
        "position_config_json": json.dumps(snap.position_config, ensure_ascii=False),
        "breadth_json": json.dumps(snap.breadth, ensure_ascii=False),
        "source": snap.source,
        "created_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    }


def build_market_state_daily(*, replace_date: bool = True) -> Path:
    snap = market_state_snapshot()
    if snap is None:
        raise RuntimeError("No market state snapshot generated.")
    row = _row(snap)
    out = pd.DataFrame([row])

    MARKET_STATE_DAILY.parent.mkdir(parents=True, exist_ok=True)
    if replace_date and MARKET_STATE_DAILY.exists():
        old = pd.read_parquet(MARKET_STATE_DAILY)
        old = old[old["trade_date"].astype(str) != row["trade_date"]]
        out = pd.concat([old, out], ignore_index=True)

    out.to_parquet(MARKET_STATE_DAILY, index=False)
    return MARKET_STATE_DAILY


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--append", action="store_true",
                         help="Do not replace rows for the same trade date.")
    args = parser.parse_args()

    path = build_market_state_daily(replace_date=not args.append)
    df = pd.read_parquet(path)
    print(f"[ok] market_state_daily rows={len(df)} path={path}")
    last = df.iloc[-1]
    print(f"  date          : {last['trade_date']}")
    print(f"  temperature   : {last['market_temperature']}")
    print(f"  state         : {last['market_state']}")
    print(f"  risk_light    : {last['risk_light']}")
    print(f"  cycle_phase   : {last['cycle_phase']}")
    print(f"  pos base/flex/config = "
          f"{last['position_base_score']:.0f} / "
          f"{last['position_flex_score']:.0f} / "
          f"{last['position_config_score']:.0f}")


if __name__ == "__main__":
    main()
