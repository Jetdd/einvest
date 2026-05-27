"""Sector cycle strength: SC30 / SC3 / SC60 and RSV (raw stochastic value).

RSV definition (the version chosen — option A from the framework distillation):

    RSV_N(t) = (close(t) - min_{N}(low)) / (max_{N}(high) - min_{N}(low)) * 100

When OHLC are not available (e.g. equal-weighted sector close series), we
fall back to close-only:

    RSV_N(t) = (close(t) - min_{N}(close)) / (max_{N}(close) - min_{N}(close)) * 100

PDF阈值参考：
    SC30 > 80 偏热 / 强势
    SC30 < 25 冰点 / 超卖
    SC3 用于短期顶底判断

Phase mapping (粗糙):
    SC30 ≥ 80 & SC3 ≥ 80   高潮
    SC30 ≥ 80 & SC3 < 50   高位回调
    SC30 50-80              抱团
    SC30 25-50              酝酿
    SC30 < 25 & SC3 < 30   冰点
    SC30 < 25 & SC3 ≥ 60   底部反弹
"""
from __future__ import annotations

import pandas as pd


def rsv(close: pd.Series, n: int,
        low: pd.Series | None = None, high: pd.Series | None = None) -> pd.Series:
    """Raw Stochastic Value over a rolling N-day window."""
    if low is None or high is None:
        low = close
        high = close
    lo = low.rolling(n, min_periods=n).min()
    hi = high.rolling(n, min_periods=n).max()
    denom = (hi - lo)
    return (100.0 * (close - lo) / denom.where(denom != 0)).astype(float)


def sc(close: pd.Series, *, sc3: int = 3, sc30: int = 30, sc60: int = 60) -> pd.DataFrame:
    """Compute SC3 / SC30 / SC60 on one close series."""
    return pd.DataFrame({
        f"SC{sc3}":  rsv(close, sc3),
        f"SC{sc30}": rsv(close, sc30),
        f"SC{sc60}": rsv(close, sc60),
    })


def classify_phase(sc30: float, sc3: float) -> str:
    """Map (SC30, SC3) to a coarse cycle phase label."""
    if pd.isna(sc30) or pd.isna(sc3):
        return "n/a"
    if sc30 >= 80 and sc3 >= 80:
        return "高潮"
    if sc30 >= 80 and sc3 < 50:
        return "高位回调"
    if sc30 >= 80:
        return "强势"
    if sc30 >= 50:
        return "抱团"
    if sc30 >= 25 and sc3 >= 60:
        return "酝酿反弹"
    if sc30 >= 25:
        return "酝酿"
    if sc3 >= 60:
        return "底部反弹"
    return "冰点"


def classify_strength(sc30: float) -> str:
    """SC30 zone label per the PDF thresholds."""
    if pd.isna(sc30):
        return "n/a"
    if sc30 >= 80:
        return "偏热"
    if sc30 >= 50:
        return "强势"
    if sc30 >= 25:
        return "中性"
    return "冰点"
