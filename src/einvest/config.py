"""Paths and constants for the einvest project."""
from __future__ import annotations

from pathlib import Path

# Local data root (reuse the dm_data root so it is consistent across projects)
DATA_ROOT = Path(r"C:\projects\data_new")
STOCK_DIR = DATA_ROOT / "stock" / "1d"
INDEX_DIR = DATA_ROOT / "index" / "1d"
FEATURE_DIR = DATA_ROOT / "features"
TAG_DIR = DATA_ROOT / "tags"
SECTOR_FEATURE_DAILY = FEATURE_DIR / "sector_feature_daily.parquet"
STOCK_TAG_SNAPSHOT = TAG_DIR / "stock_tag_snapshot.parquet"
MARKET_STATE_DAILY = FEATURE_DIR / "market_state_daily.parquet"
# Persisted full A-share universe (live codes), written by scripts/update_daily.py.
# Used for whole-market breadth / MST / 涨跌停 (vs the hot-concept universe).
FULL_A_UNIVERSE = DATA_ROOT / "meta" / "symbols" / "full_a_universe.parquet"

# einvest project paths
PROJECT_ROOT = Path(r"C:\projects\einvest")

# rqdatac credentials (reused from data_download/config.py) — used by stock fetcher
RQ_USER = "REDACTED"
RQ_PASSWORD = "REDACTED"

# Default download range
DEFAULT_START = "20200101"
