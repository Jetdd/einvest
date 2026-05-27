"""Commodity Channel Index — short-term reversal and long-term trend on indices.

CCI = (TP - SMA(TP, n)) / (0.015 * mean_dev)
where TP = (H + L + C) / 3
      mean_dev = mean(|TP - SMA(TP, n)|) over the n window.

Conventional bands:
  CCI > 100   超买（短期顶部信号）
  -100..100   中性
  CCI < -100  超卖（短期底部信号）

The framework uses CCI14 (短期择时) + CCI84 (中长期趋势确认).
"""
from __future__ import annotations

import pandas as pd


def cci(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Compute CCI from an OHLC DataFrame. Required cols: high, low, close."""
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    sma = tp.rolling(n, min_periods=n).mean()
    mean_dev = (tp - sma).abs().rolling(n, min_periods=n).mean()
    return (tp - sma) / (0.015 * mean_dev)


def classify_cci(value: float) -> str:
    """Bucket a CCI reading."""
    if pd.isna(value):
        return "n/a"
    if value > 100:
        return "超买"
    if value < -100:
        return "超卖"
    if value > 0:
        return "偏多"
    return "偏空"
