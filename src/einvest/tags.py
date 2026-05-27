"""Stock tag engine — generate trading tags from quantitative features.

Rules (framework §9.1 adapted):
  主线核心  — 所属主题 SC30>80 + 个股成交额主题内 top5 + 主题在 Top7
  强趋势    — ret_20d>主题均值 + close>MA5 + close>MA13 + amount_pct_60d>70
  高拥挤    — amount_pct_60d>90 + ret_5d>10%
  回调观察  — 主题 SC30>70 + 从20日高点回撤8-18% + close>MA13
  超跌反弹  — ret_20d<-15% + 主题 SC30<30
  右侧确认  — close>MA5 + close>MA13 + close>MA50
  放量突破  — amount_pct_20d>80 + close>MA5 + ret_1d>3%
  涨停基因  — 近5日有涨停
  缩量回调  — ret_5d<0 + amount_pct_20d<30 + close>MA13
"""
from __future__ import annotations

import json
import functools

import numpy as np
import pandas as pd

from .codes import rq_to_wind, wind_to_rq
from .cycle import cycle_detail_latest
from .io import constituents, load_stock
from .sectors import HOT_CONCEPTS
from .signals import all_signal_features


# ---------------------------------------------------------------------------
# Code normalisation
# ---------------------------------------------------------------------------

def _normalize_code(code: str) -> str:
    """Accept Wind (000001.SZ) or rqdatac (000001.XSHE) format → rqdatac."""
    c = code.strip().upper()
    if ".XSH" in c or ".XS" in c:
        return c
    return wind_to_rq(c)


# ---------------------------------------------------------------------------
# Cached reverse mapping: stock → themes
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def _stock_theme_map() -> dict[str, list[dict]]:
    """Build {rq_code: [{theme, concept}, ...]} once per session."""
    out: dict[str, list[dict]] = {}
    for theme, concepts in HOT_CONCEPTS.items():
        for concept in concepts:
            for code in constituents(concept):
                out.setdefault(code, []).append({"theme": theme, "concept": concept})
    return out


def stock_themes(stock_code: str) -> list[dict]:
    """Return [{theme, concept}, ...] for stock_code."""
    rq = _normalize_code(stock_code)
    return _stock_theme_map().get(rq, [])


# ---------------------------------------------------------------------------
# Cached theme snapshot
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def _theme_snapshot() -> dict[str, dict]:
    """Pre-compute theme/concept state for tag generation."""
    from .rankings import n_day_return, sector_close_panel

    cyc = cycle_detail_latest()
    cyc_map: dict[str, dict] = {}
    for _, row in cyc.iterrows():
        cyc_map[row["concept"]] = {
            "sc30": row.get("SC30", float("nan")),
            "sc3": row.get("SC3", float("nan")),
            "heat": row.get("heat", float("nan")),
            "phase": row.get("phase", "n/a"),
            "strength": row.get("strength", "n/a"),
            "ret_5d": row.get("ret_5d", float("nan")),
            "ret_20d": row.get("ret_20d", float("nan")),
            "theme": row.get("theme", ""),
        }

    panel = sector_close_panel()
    top7 = set()
    top7_rank: dict[str, int] = {}
    if not panel.empty and len(panel) > 5:
        rets = n_day_return(panel, 5)
        last = rets.iloc[-1].dropna().sort_values(ascending=False).head(7)
        for i, concept in enumerate(last.index, start=1):
            top7.add(concept)
            top7_rank[concept] = i

    out: dict[str, dict] = {}
    for concept, info in cyc_map.items():
        info["in_top7"] = concept in top7
        info["top7_rank"] = top7_rank.get(concept, None)
        out[concept] = info
    return out


# ---------------------------------------------------------------------------
# Amount rank within theme (cached per concept)
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def _latest_amount_map() -> dict[str, float]:
    """Latest total_turnover for every stock in the hot-concept universe."""
    all_codes: set[str] = set()
    for concepts in HOT_CONCEPTS.values():
        for concept in concepts:
            all_codes.update(constituents(concept))

    out: dict[str, float] = {}
    for code in sorted(all_codes):
        df = load_stock(code)
        if df.empty or "total_turnover" not in df.columns:
            continue
        out[code] = float(df["total_turnover"].iloc[-1])
    return out


@functools.lru_cache(maxsize=128)
def _amount_rank_map(concept: str) -> dict[str, int]:
    """Return {stock_code: rank} for all constituents of concept (1 = highest)."""
    codes = constituents(concept)
    if not codes:
        return {}

    amount_map = _latest_amount_map()
    amounts = {c: amount_map[c] for c in codes if c in amount_map}
    sorted_codes = sorted(amounts, key=amounts.get, reverse=True)
    return {c: i + 1 for i, c in enumerate(sorted_codes)}


def _amount_rank_in_theme(stock_code: str, concept: str) -> int | None:
    """Rank of stock's amount among all constituents of concept."""
    rank_map = _amount_rank_map(concept)
    return rank_map.get(stock_code, None)


# ---------------------------------------------------------------------------
# Per-stock technical features
# ---------------------------------------------------------------------------

def stock_features(stock_code: str) -> dict:
    """Compute individual stock technical features."""
    rq = _normalize_code(stock_code)
    df = load_stock(rq)
    if df.empty or len(df) < 60:
        return {}

    df = df.sort_values("date").reset_index(drop=True)
    close = df["close"]
    amt = df["total_turnover"] if "total_turnover" in df.columns else pd.Series(dtype=float)
    lu = df["limit_up"] if "limit_up" in df.columns else pd.Series(dtype=float)

    ret_1d = float(close.iloc[-1] / close.iloc[-2] - 1) * 100 if len(close) > 1 else float("nan")
    ret_5d = float(close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) > 5 else float("nan")
    ret_20d = float(close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) > 20 else float("nan")
    ret_60d = float(close.iloc[-1] / close.iloc[-61] - 1) * 100 if len(close) > 60 else float("nan")

    ma5 = close.rolling(5, min_periods=5).mean()
    ma13 = close.rolling(13, min_periods=13).mean()
    ma50 = close.rolling(50, min_periods=50).mean()

    cur_close = float(close.iloc[-1])
    above_ma5 = cur_close > float(ma5.iloc[-1]) if not pd.isna(ma5.iloc[-1]) else False
    above_ma13 = cur_close > float(ma13.iloc[-1]) if not pd.isna(ma13.iloc[-1]) else False
    above_ma50 = cur_close > float(ma50.iloc[-1]) if not pd.isna(ma50.iloc[-1]) else False

    if not amt.empty and len(amt) >= 60:
        cur_amt = float(amt.iloc[-1])
        amt_pct_20d = float((amt.tail(20) <= cur_amt).mean()) * 100
        amt_pct_60d = float((amt.tail(60) <= cur_amt).mean()) * 100
        avg_turnover_20d = float(amt.tail(20).mean())
    else:
        cur_amt = amt_pct_20d = amt_pct_60d = avg_turnover_20d = float("nan")

    high_20d = float(close.tail(20).max())
    dd = (1 - cur_close / high_20d) * 100 if high_20d > 0 else float("nan")

    has_limit = False
    if not lu.empty and "close" in df.columns:
        recent = df.tail(5)
        hits = (recent["close"] - recent["limit_up"]).abs() / recent["limit_up"].where(recent["limit_up"] > 0, 1.0)
        has_limit = (hits < 1e-3).any()

    base = {
        "code": rq,
        "wind_code": rq_to_wind(rq),
        "trade_date": df["date"].iloc[-1].date().isoformat(),
        "close": cur_close,
        "ret_1d": ret_1d,
        "ret_5d": ret_5d,
        "ret_20d": ret_20d,
        "ret_60d": ret_60d,
        "ma5": float(ma5.iloc[-1]),
        "ma13": float(ma13.iloc[-1]),
        "ma50": float(ma50.iloc[-1]),
        "above_ma5": above_ma5,
        "above_ma13": above_ma13,
        "above_ma50": above_ma50,
        "amount": cur_amt,
        "amount_pct_20d": amt_pct_20d,
        "amount_pct_60d": amt_pct_60d,
        "avg_turnover_20d": avg_turnover_20d,
        "high_20d": high_20d,
        "drawdown_from_high": dd,
        "has_limit_up_5d": has_limit,
    }
    base.update(all_signal_features(df))
    return base


# ---------------------------------------------------------------------------
# Tag generation
# ---------------------------------------------------------------------------

def _confidence(score: float) -> str:
    if pd.isna(score):
        return "low"
    if score >= 80:
        return "high"
    if score >= 60:
        return "medium"
    return "low"


def _as_jsonable(value):
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if pd.isna(value):
            return None
        return float(value)
    if pd.isna(value) if not isinstance(value, (list, dict, tuple, str)) else False:
        return None
    return value


def _add_tag(
    tags: list[str],
    evidence: dict[str, str],
    details: list[dict],
    *,
    name: str,
    category: str,
    score: float,
    summary: str,
    evidence_items: list[dict],
    evidence_type: str = "quant_feature",
    source: str = "einvest.tag_engine",
) -> None:
    tags.append(name)
    evidence[name] = summary
    details.append({
        "tag_category": category,
        "tag_name": name,
        "tag_value": True,
        "tag_score": round(float(score), 2) if not pd.isna(score) else None,
        "confidence": _confidence(score),
        "evidence_type": evidence_type,
        "evidence_id": name,
        "source": source,
        "evidence": [
            {k: _as_jsonable(v) for k, v in item.items()}
            for item in evidence_items
        ],
        "summary": summary,
    })


def generate_stock_tags(stock_code: str, *,
                          theme_snapshot: dict[str, dict] | None = None) -> dict:
    """Generate all tags + features + theme status for a stock.

    Returns:
        {
            "code": rq_code,
            "wind_code": wind_code,
            "features": {stock_features...},
            "themes": [{theme, concept, theme_state...}, ...],
            "tags": ["主线核心", "强趋势", ...],
            "tag_evidence": {"主线核心": "...", ...},
            "tag_details": [{structured tag detail...}, ...],
        }
    """
    rq = _normalize_code(stock_code)
    feats = stock_features(rq)
    if not feats:
        return {"code": rq, "wind_code": rq_to_wind(rq), "features": {},
                "themes": [], "tags": [], "tag_evidence": {}}

    themes = stock_themes(rq)
    theme_snap = theme_snapshot if theme_snapshot is not None else _theme_snapshot()

    for t in themes:
        state = theme_snap.get(t["concept"], {})
        t["sc30"] = state.get("sc30", float("nan"))
        t["sc3"] = state.get("sc3", float("nan"))
        t["heat"] = state.get("heat", float("nan"))
        t["phase"] = state.get("phase", "n/a")
        t["strength"] = state.get("strength", "n/a")
        t["in_top7"] = state.get("in_top7", False)
        t["top7_rank"] = state.get("top7_rank", None)
        t["theme_ret_20d"] = state.get("ret_20d", float("nan"))
        t["amount_rank"] = _amount_rank_in_theme(rq, t["concept"])

    tags: list[str] = []
    evidence: dict[str, str] = {}
    details: list[dict] = []

    best_theme = max(
        themes,
        key=lambda x: x.get("sc30", 0) if not pd.isna(x.get("sc30", 0)) else 0
    ) if themes else {}
    best_sc30 = best_theme.get("sc30", 0) if not pd.isna(best_theme.get("sc30", 0)) else 0
    best_in_top7 = best_theme.get("in_top7", False)
    best_amount_rank = best_theme.get("amount_rank", 999)

    # 容量焦点（蒸馏 §3.4）— 某主题 in_top7 且个股是该主题成交额 top3
    capacity_match = None
    for t in themes:
        ar = t.get("amount_rank")
        if ar is not None and ar <= 3 and t.get("in_top7"):
            if capacity_match is None or ar < capacity_match["amount_rank"]:
                capacity_match = {
                    "concept": t["concept"],
                    "theme": t["theme"],
                    "amount_rank": ar,
                    "top7_rank": t.get("top7_rank"),
                    "sc30": t.get("sc30"),
                }
    if capacity_match is not None:
        ar = capacity_match["amount_rank"]
        t7r = capacity_match["top7_rank"]
        summary = (
            f"主题「{capacity_match['concept']}」5日Top7第{t7r}名，"
            f"个股成交额主题内排名{ar}"
        )
        score = 90.0 if ar == 1 else 80.0 if ar == 2 else 72.0
        _add_tag(
            tags, evidence, details,
            name="容量焦点",
            category="trading",
            score=score,
            summary=summary,
            evidence_type="crowding_feature",
            evidence_items=[
                {"field": "concept", "value": capacity_match["concept"]},
                {"field": "amount_rank_in_theme", "value": ar, "op": "<=", "threshold": 3},
                {"field": "theme_in_top7", "value": True},
                {"field": "theme_top7_rank", "value": t7r},
            ],
        )

    # 主线核心
    if (best_sc30 > 80 and best_in_top7 and best_amount_rank is not None
            and best_amount_rank <= 5):
        summary = (
            f"所属主题「{best_theme.get('theme', '')}」SC30={best_sc30:.1f}，"
            f"位于Top7第{best_theme.get('top7_rank', 'N/A')}名，"
            f"个股成交额主题内排名{best_amount_rank}"
        )
        score = min(100.0, 0.7 * best_sc30 + 30.0 * (6 - best_amount_rank) / 5)
        _add_tag(
            tags, evidence, details,
            name="主线核心",
            category="trading",
            score=score,
            summary=summary,
            evidence_type="sector_feature",
            evidence_items=[
                {"field": "theme_sc30", "value": best_sc30, "op": ">", "threshold": 80},
                {"field": "theme_in_top7", "value": best_in_top7, "op": "=", "threshold": True},
                {"field": "amount_rank_in_theme", "value": best_amount_rank, "op": "<=", "threshold": 5},
                {"field": "concept", "value": best_theme.get("concept")},
            ],
        )

    # 强趋势
    theme_ret_20d = best_theme.get("theme_ret_20d", float("nan"))
    if (feats["ret_20d"] > theme_ret_20d
            and feats["above_ma5"] and feats["above_ma13"]
            and feats["amount_pct_60d"] > 70):
        summary = (
            f"20日涨幅 {feats['ret_20d']:.1f}% > 主题均值 {theme_ret_20d:.1f}%，"
            f"站上MA5/MA13，成交额60日分位 {feats['amount_pct_60d']:.0f}%"
        )
        score = min(100.0, max(0.0, 50.0 + (feats["ret_20d"] - theme_ret_20d)) + 0.3 * feats["amount_pct_60d"])
        _add_tag(
            tags, evidence, details,
            name="强趋势",
            category="trading",
            score=score,
            summary=summary,
            evidence_items=[
                {"field": "ret_20d", "value": feats["ret_20d"], "op": ">", "threshold": theme_ret_20d},
                {"field": "above_ma5", "value": feats["above_ma5"], "op": "=", "threshold": True},
                {"field": "above_ma13", "value": feats["above_ma13"], "op": "=", "threshold": True},
                {"field": "amount_pct_60d", "value": feats["amount_pct_60d"], "op": ">", "threshold": 70},
            ],
        )

    # 高拥挤
    if feats["amount_pct_60d"] > 90 and feats["ret_5d"] > 10:
        summary = (
            f"成交额60日分位 {feats['amount_pct_60d']:.0f}% > 90，"
            f"5日涨幅 {feats['ret_5d']:.1f}% > 10%"
        )
        score = min(100.0, 0.7 * feats["amount_pct_60d"] + 1.5 * feats["ret_5d"])
        _add_tag(
            tags, evidence, details,
            name="高拥挤",
            category="risk",
            score=score,
            summary=summary,
            evidence_items=[
                {"field": "amount_pct_60d", "value": feats["amount_pct_60d"], "op": ">", "threshold": 90},
                {"field": "ret_5d", "value": feats["ret_5d"], "op": ">", "threshold": 10},
            ],
        )

    # 回调观察
    dd = feats["drawdown_from_high"]
    if (best_sc30 > 70 and 8 <= dd <= 18 and feats["above_ma13"]):
        summary = (
            f"主题SC30={best_sc30:.1f}仍强，"
            f"个股从20日高点回撤 {dd:.1f}%，仍在MA13上方"
        )
        score = min(100.0, 0.6 * best_sc30 + 40.0 * (1 - abs(dd - 13) / 10))
        _add_tag(
            tags, evidence, details,
            name="回调观察",
            category="trading",
            score=score,
            summary=summary,
            evidence_items=[
                {"field": "theme_sc30", "value": best_sc30, "op": ">", "threshold": 70},
                {"field": "drawdown_from_high", "value": dd, "op": "between", "threshold": [8, 18]},
                {"field": "above_ma13", "value": feats["above_ma13"], "op": "=", "threshold": True},
            ],
        )

    # 超跌反弹
    if feats["ret_20d"] < -15 and best_sc30 < 30:
        summary = (
            f"20日跌幅 {feats['ret_20d']:.1f}% < -15%，"
            f"主题SC30={best_sc30:.1f}处于冰点"
        )
        score = min(100.0, abs(feats["ret_20d"]) * 2 + (30 - best_sc30))
        _add_tag(
            tags, evidence, details,
            name="超跌反弹",
            category="trading",
            score=score,
            summary=summary,
            evidence_items=[
                {"field": "ret_20d", "value": feats["ret_20d"], "op": "<", "threshold": -15},
                {"field": "theme_sc30", "value": best_sc30, "op": "<", "threshold": 30},
            ],
        )

    # 右侧确认
    if feats["above_ma5"] and feats["above_ma13"] and feats["above_ma50"]:
        _add_tag(
            tags, evidence, details,
            name="右侧确认",
            category="trading",
            score=75.0,
            summary="收盘价站上MA5、MA13、MA50",
            evidence_items=[
                {"field": "above_ma5", "value": feats["above_ma5"], "op": "=", "threshold": True},
                {"field": "above_ma13", "value": feats["above_ma13"], "op": "=", "threshold": True},
                {"field": "above_ma50", "value": feats["above_ma50"], "op": "=", "threshold": True},
            ],
        )

    # 放量突破
    if feats["amount_pct_20d"] > 80 and feats["above_ma5"] and feats["ret_1d"] > 3:
        summary = (
            f"成交额20日分位 {feats['amount_pct_20d']:.0f}% > 80，"
            f"站上MA5，今日涨幅 {feats['ret_1d']:.1f}% > 3%"
        )
        score = min(100.0, 0.6 * feats["amount_pct_20d"] + 8 * feats["ret_1d"])
        _add_tag(
            tags, evidence, details,
            name="放量突破",
            category="trading",
            score=score,
            summary=summary,
            evidence_items=[
                {"field": "amount_pct_20d", "value": feats["amount_pct_20d"], "op": ">", "threshold": 80},
                {"field": "above_ma5", "value": feats["above_ma5"], "op": "=", "threshold": True},
                {"field": "ret_1d", "value": feats["ret_1d"], "op": ">", "threshold": 3},
            ],
        )

    # 涨停基因
    if feats["has_limit_up_5d"]:
        _add_tag(
            tags, evidence, details,
            name="涨停基因",
            category="trading",
            score=70.0,
            summary="近5日内触及涨停",
            evidence_items=[
                {"field": "has_limit_up_5d", "value": feats["has_limit_up_5d"], "op": "=", "threshold": True},
            ],
        )

    # 缩量回调
    if feats["ret_5d"] < 0 and feats["amount_pct_20d"] < 30 and feats["above_ma13"]:
        summary = (
            f"5日回调 {feats['ret_5d']:.1f}%，"
            f"成交额20日分位 {feats['amount_pct_20d']:.0f}% < 30，"
            f"仍在MA13上方"
        )
        score = min(100.0, 60.0 + (30 - feats["amount_pct_20d"]) + min(10, abs(feats["ret_5d"])))
        _add_tag(
            tags, evidence, details,
            name="缩量回调",
            category="trading",
            score=score,
            summary=summary,
            evidence_items=[
                {"field": "ret_5d", "value": feats["ret_5d"], "op": "<", "threshold": 0},
                {"field": "amount_pct_20d", "value": feats["amount_pct_20d"], "op": "<", "threshold": 30},
                {"field": "above_ma13", "value": feats["above_ma13"], "op": "=", "threshold": True},
            ],
        )

    # -----------------------------------------------------------------------
    # §10.5 趋势卡位 — 大牛卡位线 + 长波回档线
    # -----------------------------------------------------------------------
    above_cap = feats.get("above_trend_cap")
    above_retrace = feats.get("above_retrace_line")
    recent_event = feats.get("recent_limit_up_10d") or feats.get("recent_volume_surge_10d")
    if above_cap and above_retrace and recent_event:
        is_premium = bool(feats.get("retrace_above_cap"))
        cap = feats.get("trend_cap_line")
        retrace = feats.get("retrace_line")
        evt_desc = (
            "近10日涨停" if feats.get("recent_limit_up_10d") else
            f"近10日放量(>1.5x均量)"
        )
        if is_premium:
            name = "趋势卡位精选"
            summary = (
                f"价站上大牛卡位 {cap:.2f}（长波回档 {retrace:.2f} 在卡位上方），"
                f"{evt_desc}"
            )
            score = 90.0
        else:
            name = "趋势卡位买点"
            summary = (
                f"价站上大牛卡位 {cap:.2f} 与长波回档 {retrace:.2f}，"
                f"{evt_desc}"
            )
            score = 75.0
        _add_tag(
            tags, evidence, details,
            name=name,
            category="trading",
            score=score,
            summary=summary,
            evidence_items=[
                {"field": "trend_cap_line", "value": cap},
                {"field": "retrace_line", "value": retrace},
                {"field": "above_trend_cap", "value": above_cap, "op": "=", "threshold": True},
                {"field": "above_retrace_line", "value": above_retrace, "op": "=", "threshold": True},
                {"field": "retrace_above_cap", "value": is_premium},
                {"field": "recent_limit_up_10d", "value": feats.get("recent_limit_up_10d")},
                {"field": "recent_volume_surge_10d", "value": feats.get("recent_volume_surge_10d")},
            ],
        )

    # -----------------------------------------------------------------------
    # §10.6 5 层抄底 — 绝底 / 超高 / 高 / 中高 / 中
    # -----------------------------------------------------------------------
    daily_ret = feats.get("daily_ret_today")
    amplitude = feats.get("amplitude_today")
    body_ret = feats.get("body_ret_today")
    bias_34 = feats.get("bias_34")

    # 绝底 95%
    if (bias_34 is not None and amplitude is not None and body_ret is not None
            and daily_ret is not None
            and bias_34 < -25 and amplitude > 6 and body_ret > 4 and daily_ret > 3):
        summary = (
            f"34日乖离 {bias_34:.1f}%（<-25），振幅 {amplitude:.1f}%，"
            f"实体涨幅 {body_ret:.1f}%，日涨 {daily_ret:.1f}%"
        )
        _add_tag(
            tags, evidence, details,
            name="抄底·绝底(95)",
            category="trading",
            score=95.0,
            summary=summary,
            evidence_items=[
                {"field": "bias_34", "value": bias_34, "op": "<", "threshold": -25},
                {"field": "amplitude_today", "value": amplitude, "op": ">", "threshold": 6},
                {"field": "body_ret_today", "value": body_ret, "op": ">", "threshold": 4},
                {"field": "daily_ret_today", "value": daily_ret, "op": ">", "threshold": 3},
            ],
        )

    # 超高概率 87%（21EMA偏离率上穿 -20）
    if (feats.get("cross_up_ema21_minus20") and daily_ret is not None and daily_ret > 2):
        summary = (
            f"21日EMA偏离率上穿 -20（当前 {feats.get('bias_ema21'):.1f}%），"
            f"日涨 {daily_ret:.1f}%"
        )
        _add_tag(
            tags, evidence, details,
            name="抄底·超高(87)",
            category="trading",
            score=87.0,
            summary=summary,
            evidence_items=[
                {"field": "cross_up_ema21_minus20", "value": True},
                {"field": "bias_ema21", "value": feats.get("bias_ema21")},
                {"field": "daily_ret_today", "value": daily_ret, "op": ">", "threshold": 2},
            ],
        )

    # 高概率 81%（24MA偏离率上穿 -20）
    if (feats.get("cross_up_ma24_minus20") and daily_ret is not None and daily_ret > 2):
        summary = (
            f"24日MA偏离率上穿 -20（当前 {feats.get('bias_ma24'):.1f}%），"
            f"日涨 {daily_ret:.1f}%"
        )
        _add_tag(
            tags, evidence, details,
            name="抄底·高(81)",
            category="trading",
            score=81.0,
            summary=summary,
            evidence_items=[
                {"field": "cross_up_ma24_minus20", "value": True},
                {"field": "bias_ma24", "value": feats.get("bias_ma24")},
                {"field": "daily_ret_today", "value": daily_ret, "op": ">", "threshold": 2},
            ],
        )

    # 中高 68%（120日新低 + 涨幅）
    if (feats.get("new_low_120d_3d") and daily_ret is not None and daily_ret > 2):
        summary = f"近3日低点创120日新低，日涨 {daily_ret:.1f}%"
        _add_tag(
            tags, evidence, details,
            name="抄底·中高(68)",
            category="trading",
            score=68.0,
            summary=summary,
            evidence_items=[
                {"field": "new_low_120d_3d", "value": True},
                {"field": "daily_ret_today", "value": daily_ret, "op": ">", "threshold": 2},
            ],
        )

    # 中 60%（60日新低 + 涨幅）
    if (feats.get("new_low_60d_3d") and daily_ret is not None and daily_ret > 2
            and not feats.get("new_low_120d_3d")):  # 避免与中高重复
        summary = f"近3日低点创60日新低，日涨 {daily_ret:.1f}%"
        _add_tag(
            tags, evidence, details,
            name="抄底·中(60)",
            category="trading",
            score=60.0,
            summary=summary,
            evidence_items=[
                {"field": "new_low_60d_3d", "value": True},
                {"field": "daily_ret_today", "value": daily_ret, "op": ">", "threshold": 2},
            ],
        )

    # -----------------------------------------------------------------------
    # §10.7 情绪龙头 — 涨停 / 连板 / 夺命板 / 攻击资金
    # -----------------------------------------------------------------------
    consecutive_lu = feats.get("consecutive_limit_up", 0) or 0

    # 涨停（今日）
    if feats.get("is_limit_up_today"):
        name = f"连板·{consecutive_lu}板" if consecutive_lu >= 2 else "涨停"
        _add_tag(
            tags, evidence, details,
            name=name,
            category="trading",
            score=min(100.0, 70.0 + 5.0 * consecutive_lu),
            summary=f"今日封板，{consecutive_lu} 连板",
            evidence_items=[
                {"field": "is_limit_up_today", "value": True},
                {"field": "consecutive_limit_up", "value": consecutive_lu},
            ],
        )

    # 夺命板
    if feats.get("dou_ming_ban"):
        _add_tag(
            tags, evidence, details,
            name="夺命板",
            category="trading",
            score=88.0,
            summary="昨缩今放(<2x) + 上穿21日MA + 涨停",
            evidence_items=[
                {"field": "dou_ming_ban", "value": True},
                {"field": "is_limit_up_today", "value": True},
                {"field": "cross_up_ma21", "value": True},
            ],
        )

    # 攻击资金（短EMA - 长EMA 上升 + 工作线之上）
    if (feats.get("attack_rising") and feats.get("above_work_line")
            and feats.get("work_above_rest")):
        atk = feats.get("attack_capital")
        _add_tag(
            tags, evidence, details,
            name="攻击资金共振",
            category="trading",
            score=78.0,
            summary=f"攻击资金 {atk:.3f} 上升，价站工作线，工作线>度假线",
            evidence_items=[
                {"field": "attack_capital", "value": atk},
                {"field": "attack_rising", "value": True},
                {"field": "above_work_line", "value": True},
                {"field": "work_above_rest", "value": True},
            ],
        )

    return {
        "code": rq,
        "wind_code": rq_to_wind(rq),
        "features": feats,
        "themes": themes,
        "tags": tags,
        "tag_evidence": evidence,
        "tag_details": details,
    }


def tag_snapshot_rows(result: dict, *, created_at: str | None = None) -> list[dict]:
    """Convert one generate_stock_tags result to stock_tag_snapshot rows."""
    feats = result.get("features") or {}
    if not feats:
        return []
    if created_at is None:
        created_at = pd.Timestamp.now().isoformat(timespec="seconds")

    rows: list[dict] = []
    trade_date = feats.get("trade_date")
    symbol = result["code"]
    for detail in result.get("tag_details", []):
        rows.append({
            "trade_date": trade_date,
            "symbol": symbol,
            "wind_code": result["wind_code"],
            "tag_category": detail["tag_category"],
            "tag_name": detail["tag_name"],
            "tag_value": detail["tag_value"],
            "tag_score": detail["tag_score"],
            "confidence": detail["confidence"],
            "evidence_type": detail["evidence_type"],
            "evidence_id": detail["evidence_id"],
            "evidence_json": json.dumps(detail["evidence"], ensure_ascii=False),
            "summary": detail["summary"],
            "source": detail["source"],
            "created_at": created_at,
        })
    return rows


# ---------------------------------------------------------------------------
# Batch tag generation for a stock pool
# ---------------------------------------------------------------------------

def tag_pool(codes: list[str]) -> pd.DataFrame:
    """Generate tags for a list of stocks, return as a DataFrame."""
    rows: list[dict] = []
    for code in codes:
        result = generate_stock_tags(code)
        feats = result["features"]
        if not feats:
            continue
        rows.append({
            "code": result["code"],
            "wind_code": result["wind_code"],
            "close": feats["close"],
            "ret_1d": feats["ret_1d"],
            "ret_5d": feats["ret_5d"],
            "ret_20d": feats["ret_20d"],
            "amount_pct_60d": feats["amount_pct_60d"],
            "drawdown": feats["drawdown_from_high"],
            "above_ma5": feats["above_ma5"],
            "above_ma13": feats["above_ma13"],
            "above_ma50": feats["above_ma50"],
            "tags": ",".join(result["tags"]),
            "n_tags": len(result["tags"]),
        })
    return pd.DataFrame(rows)
