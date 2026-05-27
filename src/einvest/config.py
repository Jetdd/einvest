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

# einvest project paths
PROJECT_ROOT = Path(r"C:\projects\einvest")

# rqdatac credentials (reused from data_download/config.py) — used by stock fetcher
RQ_USER = "REDACTED"
RQ_PASSWORD = "REDACTED"

# Default download range
DEFAULT_START = "20200101"
