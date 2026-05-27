"""Build stock_tag_snapshot from the current einvest tag engine.

Output:
    C:\projects\data_new\tags\stock_tag_snapshot.parquet
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from einvest.config import STOCK_TAG_SNAPSHOT
from einvest.io import universe
from einvest.tags import _theme_snapshot, generate_stock_tags, tag_snapshot_rows


def _batched(items: list[str], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def build_stock_tag_snapshot(
    *,
    codes: list[str] | None = None,
    limit: int | None = None,
    replace_date: bool = True,
    batch_size: int = 200,
) -> Path:
    selected = list(codes) if codes is not None else universe()
    if limit is not None:
        selected = selected[:limit]
    if not selected:
        raise RuntimeError("No stock universe selected.")

    theme_snapshot = _theme_snapshot()
    created_at = pd.Timestamp.now().isoformat(timespec="seconds")
    rows: list[dict] = []

    for batch in _batched(selected, batch_size):
        for code in batch:
            result = generate_stock_tags(code, theme_snapshot=theme_snapshot)
            rows.extend(tag_snapshot_rows(result, created_at=created_at))

    out = pd.DataFrame(rows)
    if out.empty:
        out = pd.DataFrame(columns=[
            "trade_date", "symbol", "wind_code", "tag_category", "tag_name",
            "tag_value", "tag_score", "confidence", "evidence_type",
            "evidence_id", "evidence_json", "summary", "source", "created_at",
        ])
        trade_date = None
    else:
        trade_date = str(out["trade_date"].dropna().max())

    STOCK_TAG_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    if replace_date and trade_date and STOCK_TAG_SNAPSHOT.exists():
        old = pd.read_parquet(STOCK_TAG_SNAPSHOT)
        old = old[old["trade_date"].astype(str) != trade_date]
        out = pd.concat([old, out], ignore_index=True)

    out.to_parquet(STOCK_TAG_SNAPSHOT, index=False)
    return STOCK_TAG_SNAPSHOT


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codes", nargs="*", help="Optional rqdatac/Wind stock codes.")
    parser.add_argument("--limit", type=int, default=None, help="Limit universe size for smoke runs.")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--append", action="store_true", help="Do not replace rows for the same trade date.")
    args = parser.parse_args()

    path = build_stock_tag_snapshot(
        codes=args.codes,
        limit=args.limit,
        replace_date=not args.append,
        batch_size=args.batch_size,
    )
    df = pd.read_parquet(path)
    print(f"[ok] stock_tag_snapshot rows={len(df)} path={path}")
    if not df.empty:
        latest = df[df["trade_date"].astype(str) == str(df["trade_date"].max())]
        print(latest["tag_name"].value_counts().head(20).to_string())


if __name__ == "__main__":
    main()
