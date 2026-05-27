"""Per-stock signal features — trend cap / bottom / emotion leader.

Per framework distillation §10.5 / §10.6 / §10.7. Each function consumes a
single-stock OHLCV DataFrame (rqdatac parquet schema: open/high/low/close/
prev_close/limit_up/limit_down/volume/total_turnover) and returns a flat dict
of the features needed at the last bar.

These are *feature* computations — tag rules live in tags.py and decide which
features fire which tag.
"""
from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_last(s: pd.Series) -> float:
    if s.empty:
        return float("nan")
    v = s.iloc[-1]
    return float(v) if not pd.isna(v) else float("nan")


def _is_limit_up(close: pd.Series, lim_up: pd.Series, tol: float = 1e-3) -> pd.Series:
    """Boolean Series: each bar's close hits its limit_up (within `tol` rel)."""
    if close.empty or lim_up.empty:
        return pd.Series(False, index=close.index)
    rel = (close - lim_up).abs() / lim_up.where(lim_up != 0, 1.0)
    return rel < tol


# ---------------------------------------------------------------------------
# §10.5 Trend Cap (趋势牛卡位)
# ---------------------------------------------------------------------------

def trend_cap_features(df: pd.DataFrame) -> dict:
    """大牛卡位 + 长波回档 + 触发条件特征.

    大牛卡位 = EMA(HHV(close, 10), 30) * 0.98
    长波回档 = EMA(close, 17) * 0.96
    """
    if df.empty or len(df) < 60:
        return {}
    close = df["close"]
    vol = df["volume"] if "volume" in df.columns else df["total_turnover"]
    lim_up = df["limit_up"] if "limit_up" in df.columns else pd.Series(dtype=float)

    hhv10 = close.rolling(10, min_periods=10).max()
    ema30_hhv10 = hhv10.ewm(span=30, adjust=False, min_periods=30).mean()
    trend_cap_line = ema30_hhv10 * 0.98

    ema17 = close.ewm(span=17, adjust=False, min_periods=17).mean()
    retrace_line = ema17 * 0.96

    vol_avg_120 = vol.rolling(120, min_periods=60).mean()
    vol_ratio = vol / vol_avg_120

    is_lu = _is_limit_up(close, lim_up) if not lim_up.empty else pd.Series(False, index=close.index)
    recent_limit_up_10d = is_lu.tail(10).any() if len(is_lu) >= 1 else False
    recent_volume_surge_10d = (vol_ratio.tail(10) > 1.5).any() if len(vol_ratio) >= 10 else False

    cur_close = _safe_last(close)
    cur_cap = _safe_last(trend_cap_line)
    cur_retrace = _safe_last(retrace_line)
    cur_vol_ratio = _safe_last(vol_ratio)

    above_cap = (not pd.isna(cur_cap)) and cur_close > cur_cap
    above_retrace = (not pd.isna(cur_retrace)) and cur_close > cur_retrace
    retrace_above_cap = (not pd.isna(cur_retrace) and not pd.isna(cur_cap)
                          and cur_retrace > cur_cap)

    return {
        "trend_cap_line": round(cur_cap, 3) if not pd.isna(cur_cap) else None,
        "retrace_line": round(cur_retrace, 3) if not pd.isna(cur_retrace) else None,
        "above_trend_cap": bool(above_cap),
        "above_retrace_line": bool(above_retrace),
        "retrace_above_cap": bool(retrace_above_cap),
        "vol_ratio_120d": round(cur_vol_ratio, 2) if not pd.isna(cur_vol_ratio) else None,
        "recent_limit_up_10d": bool(recent_limit_up_10d),
        "recent_volume_surge_10d": bool(recent_volume_surge_10d),
    }


# ---------------------------------------------------------------------------
# §10.6 Bottom — 5-level high-win-rate (高胜率抄底)
# ---------------------------------------------------------------------------

def bottom_features(df: pd.DataFrame) -> dict:
    """BIAS + 振幅/实体涨幅 + 60/120日新低 — 5 层抄底前置特征."""
    if df.empty or len(df) < 130:
        return {}
    close = df["close"]
    high = df["high"]
    low = df["low"]
    op = df["open"]
    pc = df["prev_close"]

    ma34 = close.rolling(34, min_periods=34).mean()
    ema21 = close.ewm(span=21, adjust=False, min_periods=21).mean()
    ma24 = close.rolling(24, min_periods=24).mean()

    bias_34 = (close - ma34) / ma34 * 100
    bias_ema21 = (close - ema21) / ema21 * 100
    bias_ma24 = (close - ma24) / ma24 * 100

    daily_ret = (close - pc) / pc * 100
    amplitude = (high - low) / pc * 100
    body_ret = (close - op) / pc * 100

    # 新低判断（排除最近3日，比较最近3日最低 vs 60/120日同期最低）
    if len(low) >= 123:
        low_3d_min_now = float(low.tail(3).min())
        low_60d_min_excl = float(low.iloc[-63:-3].min())
        low_120d_min_excl = float(low.iloc[-123:-3].min())
        new_low_60d = low_3d_min_now < low_60d_min_excl
        new_low_120d = low_3d_min_now < low_120d_min_excl
    else:
        new_low_60d = new_low_120d = False

    # 上穿判断
    cur_bias_ema21 = _safe_last(bias_ema21)
    prev_bias_ema21 = float(bias_ema21.iloc[-2]) if len(bias_ema21) > 1 and not pd.isna(bias_ema21.iloc[-2]) else float("nan")
    cross_up_ema21_minus20 = (not pd.isna(prev_bias_ema21) and not pd.isna(cur_bias_ema21)
                                and prev_bias_ema21 < -20 and cur_bias_ema21 >= -20)

    cur_bias_ma24 = _safe_last(bias_ma24)
    prev_bias_ma24 = float(bias_ma24.iloc[-2]) if len(bias_ma24) > 1 and not pd.isna(bias_ma24.iloc[-2]) else float("nan")
    cross_up_ma24_minus20 = (not pd.isna(prev_bias_ma24) and not pd.isna(cur_bias_ma24)
                               and prev_bias_ma24 < -20 and cur_bias_ma24 >= -20)

    return {
        "bias_34": round(_safe_last(bias_34), 2) if not pd.isna(_safe_last(bias_34)) else None,
        "bias_ema21": round(cur_bias_ema21, 2) if not pd.isna(cur_bias_ema21) else None,
        "bias_ma24": round(cur_bias_ma24, 2) if not pd.isna(cur_bias_ma24) else None,
        "cross_up_ema21_minus20": bool(cross_up_ema21_minus20),
        "cross_up_ma24_minus20": bool(cross_up_ma24_minus20),
        "amplitude_today": round(_safe_last(amplitude), 2) if not pd.isna(_safe_last(amplitude)) else None,
        "body_ret_today": round(_safe_last(body_ret), 2) if not pd.isna(_safe_last(body_ret)) else None,
        "daily_ret_today": round(_safe_last(daily_ret), 2) if not pd.isna(_safe_last(daily_ret)) else None,
        "new_low_60d_3d": bool(new_low_60d),
        "new_low_120d_3d": bool(new_low_120d),
    }


# ---------------------------------------------------------------------------
# §10.7 Emotion Leader (擒龙捉妖)
# ---------------------------------------------------------------------------

def emotion_features(df: pd.DataFrame) -> dict:
    """涨停识别 + 夺命板 + 工作/度假线 + 攻击资金 — 情绪龙头特征.

    工作线 = EMA((L+H+2C)/4, 14)
    度假线 = EMA((L+H+2C)/4, 25)
    攻击资金 = EMA(close, 5) - EMA(close, 21)
    """
    if df.empty or len(df) < 30:
        return {}
    close = df["close"]
    high = df["high"]
    low = df["low"]
    vol = df["volume"] if "volume" in df.columns else df["total_turnover"]
    lim_up = df["limit_up"] if "limit_up" in df.columns else pd.Series(dtype=float)

    # 涨停识别
    is_lu = _is_limit_up(close, lim_up) if not lim_up.empty else pd.Series(False, index=close.index)
    is_lu_today = bool(is_lu.iloc[-1]) if len(is_lu) > 0 else False
    consecutive_lu = 0
    if not is_lu.empty:
        for v in is_lu.iloc[::-1]:
            if bool(v):
                consecutive_lu += 1
            else:
                break

    # 夺命板：昨日缩量 → 今日放量但<2倍 + 上穿21日MA + 今日涨停
    ma21 = close.rolling(21, min_periods=21).mean()
    if len(vol) > 2 and len(ma21) > 1:
        vol_t = float(vol.iloc[-1])
        vol_t1 = float(vol.iloc[-2])
        vol_t2 = float(vol.iloc[-3]) if len(vol) > 2 else float("nan")
        vol_yest_shrunk = (not pd.isna(vol_t2)) and vol_t1 < vol_t2
        vol_today_expand = (vol_t1 > 0) and (1.0 < vol_t / vol_t1 < 2.0)
        prev_close = float(close.iloc[-2])
        prev_ma21 = float(ma21.iloc[-2]) if not pd.isna(ma21.iloc[-2]) else float("nan")
        cur_ma21 = float(ma21.iloc[-1]) if not pd.isna(ma21.iloc[-1]) else float("nan")
        cur_close_val = float(close.iloc[-1])
        cross_up_ma21 = (not pd.isna(prev_ma21) and not pd.isna(cur_ma21)
                          and prev_close < prev_ma21 and cur_close_val > cur_ma21)
        dou_ming_ban = bool(is_lu_today and vol_yest_shrunk and vol_today_expand and cross_up_ma21)
    else:
        dou_ming_ban = False
        cross_up_ma21 = False

    # 工作/度假线
    typical = (low + high + 2 * close) / 4
    work_line = typical.ewm(span=14, adjust=False, min_periods=14).mean()
    rest_line = typical.ewm(span=25, adjust=False, min_periods=25).mean()
    cur_close = _safe_last(close)
    cur_work = _safe_last(work_line)
    cur_rest = _safe_last(rest_line)
    above_work = (not pd.isna(cur_work)) and cur_close > cur_work
    work_above_rest = (not pd.isna(cur_work) and not pd.isna(cur_rest)
                        and cur_work > cur_rest)

    # 攻击资金
    ema5 = close.ewm(span=5, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False, min_periods=21).mean()
    attack = ema5 - ema21
    cur_attack = _safe_last(attack)
    prev_attack = float(attack.iloc[-2]) if len(attack) > 1 and not pd.isna(attack.iloc[-2]) else float("nan")
    attack_rising = (not pd.isna(prev_attack) and not pd.isna(cur_attack)
                      and cur_attack > prev_attack and cur_attack > 0)

    return {
        "is_limit_up_today": is_lu_today,
        "consecutive_limit_up": int(consecutive_lu),
        "dou_ming_ban": dou_ming_ban,
        "cross_up_ma21": bool(cross_up_ma21),
        "work_line": round(cur_work, 3) if not pd.isna(cur_work) else None,
        "rest_line": round(cur_rest, 3) if not pd.isna(cur_rest) else None,
        "above_work_line": bool(above_work),
        "work_above_rest": bool(work_above_rest),
        "attack_capital": round(cur_attack, 4) if not pd.isna(cur_attack) else None,
        "attack_rising": bool(attack_rising),
    }


# ---------------------------------------------------------------------------
# Combined entry — call from tags.stock_features
# ---------------------------------------------------------------------------

def all_signal_features(df: pd.DataFrame) -> dict:
    """Return trend + bottom + emotion features merged."""
    out: dict = {}
    out.update(trend_cap_features(df))
    out.update(bottom_features(df))
    out.update(emotion_features(df))
    return out
