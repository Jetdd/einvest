"""Liquidity layer.

Inputs (per the framework):
- 全市场总成交额 (sum of daily total_turnover across the universe)
- 平均换手率 (avg turnover ratio across the universe — we don't have it for now;
  use volume / shares-out as a proxy if needed later)

We score liquidity as the rolling quantile of total daily amount over a window,
then bucket into 匮乏 / 充足 / 溢出 by PDF thresholds (<45 / 45-90 / >90).
"""
from __future__ import annotations

import pandas as pd


def total_amount(amount_panel: pd.DataFrame) -> pd.Series:
    """Sum daily amount across columns. Missing values treated as 0."""
    return amount_panel.fillna(0.0).sum(axis=1)


def liquidity_score(total_amt: pd.Series, window: int = 252) -> pd.Series:
    """Rolling 0-100 percentile rank of total daily amount over `window` days.

    Each value's rank (pct=True) within the trailing window, scaled to 0-100.
    """
    return total_amt.rolling(window, min_periods=20).rank(pct=True).mul(100.0)


def liquidity_band(score: float) -> str:
    """Bucket per PDF thresholds: <45 匮乏, 45-90 充足, >90 溢出."""
    if pd.isna(score):
        return "n/a"
    if score < 45:
        return "匮乏"
    if score > 90:
        return "溢出"
    return "充足"
