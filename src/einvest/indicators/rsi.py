"""RSI (Wilder) and EMA helper — used to build the sector heatmap.

Heatmap recipe (per einvest article):
    heat(t) = EMA(RSI(close, 14), 5)
"""
from __future__ import annotations

import pandas as pd


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder's RSI on a single close series."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    # Wilder smoothing == EMA with alpha = 1/n
    avg_gain = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    out = 100 - (100 / (1 + rs))
    return out.astype(float)


def rsi_ema(close: pd.Series, n_rsi: int = 14, n_ema: int = 5) -> pd.Series:
    """RSI(n_rsi) then EMA(n_ema) — the einvest heatmap heat value."""
    r = rsi(close, n_rsi)
    return r.ewm(span=n_ema, adjust=False, min_periods=n_ema).mean()
