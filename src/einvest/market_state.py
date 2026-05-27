"""Market state composite — CCI / MST / Liquidity / Breadth / Sector phase
into a unified dashboard panel.

Per the framework distillation §3 + §10:

  market_temperature  : 0-100 composite score
  market_state        : 强势进攻 / 偏多震荡 / 偏空震荡 / 退潮防守
  risk_light          : 绿 / 黄 / 红  (rule-based; historical-similarity
                        scoring is deferred to the signal-backtest phase)
  position_base       : 0-100, index MA matrix (5/13/50)
  position_flex       : 0-100, MST + CCI + liquidity
  position_config     : 0-100, # strong sectors (SC30≥50)
  cycle_phase         : 酝酿 / 抱团 / 主流轮动 / 高潮 / 缩容 / 瓦解 / 中性
                        (market-level — based on top主线 SC30 + breadth +
                         涨停 + liquidity)

NOTE: the PDF's literal v5 state machine (B1/R1/B2/B2_EXIT) needs transition
rules that aren't in the distillation, so cycle_phase is the closest
reproducible substitute (蒸馏 §0 / §17).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import pandas as pd

from .cycle import cycle_detail_latest
from .indicators import (
    cci,
    classify_cci,
    liquidity_band,
    liquidity_score,
    mst,
    up_down_count,
)
from .indicators.sc import rsv
from .io import load_close_panel, load_full_a, load_index, universe
from .sectors import MAIN_INDICES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cci_to_flex(cci84: float) -> float:
    """Map CCI84 to a 0-100 flex contribution.

    > 150       overbought / 派发风险      → 30
    50..150     偏多                       → 75
    0..50       中性偏多                   → 60
    -100..0     偏空                       → 40
    < -100      超卖                       → 25 (might be 底部 but no entry yet)
    """
    if pd.isna(cci84):
        return 50.0
    if cci84 > 150:
        return 30.0
    if cci84 > 50:
        return 75.0
    if cci84 > 0:
        return 60.0
    if cci84 > -100:
        return 40.0
    return 25.0


def _liq_to_flex(liq_score: float) -> float:
    """Map liquidity score to a 0-100 flex contribution.

    >90    溢出 / 派发风险   → 50
    45-90  充足              → 75
    <45    匮乏              → 30
    """
    if pd.isna(liq_score):
        return 50.0
    if liq_score > 90:
        return 50.0
    if liq_score > 45:
        return 75.0
    return 30.0


def _pct_strong_to_config(pct_strong: float) -> float:
    """Map % of sectors with SC30≥50 to a 0-100 config position score."""
    if pct_strong >= 0.40:
        return 95.0
    if pct_strong >= 0.30:
        return 80.0
    if pct_strong >= 0.20:
        return 60.0
    if pct_strong >= 0.10:
        return 35.0
    return 15.0


# ---------------------------------------------------------------------------
# Position components
# ---------------------------------------------------------------------------

def position_base(index_codes: list[str] | None = None) -> dict[str, Any]:
    """Base position from index MA matrix.

    For each main index, count how many of (MA5, MA13, MA50) the close is
    above. Aggregate across indices → 0-100.
    """
    codes = index_codes or list(MAIN_INDICES.values())
    name_lookup = {v: k for k, v in MAIN_INDICES.items()}
    scores: list[float] = []
    details: list[dict[str, Any]] = []
    for code in codes:
        df = load_index(code)
        if df.empty or len(df) < 50:
            continue
        close = df["close"]
        ma5 = float(close.rolling(5, min_periods=5).mean().iloc[-1])
        ma13 = float(close.rolling(13, min_periods=13).mean().iloc[-1])
        ma50 = float(close.rolling(50, min_periods=50).mean().iloc[-1])
        cur = float(close.iloc[-1])
        flags = (cur > ma5, cur > ma13, cur > ma50)
        cnt = sum(flags)
        scores.append(cnt / 3.0)
        details.append({
            "code": code,
            "name": name_lookup.get(code, code),
            "close": round(cur, 2),
            "above_ma5": flags[0],
            "above_ma13": flags[1],
            "above_ma50": flags[2],
            "above_count": cnt,
        })
    avg = sum(scores) / len(scores) if scores else 0.0
    return {
        "score": round(avg * 100, 1),
        "n_indices": len(scores),
        "details": details,
    }


def position_flex(*, full_a_amt: pd.Series, mst_df: pd.DataFrame,
                   index_for_cci: str = "000001.XSHG") -> dict[str, Any]:
    """Flex position from MST + CCI + liquidity (each weighted equally)."""
    mst5 = float(mst_df["MST_5"].iloc[-1])
    mst13 = float(mst_df["MST_13"].iloc[-1])
    mst50 = float(mst_df["MST_50"].iloc[-1])
    mst_avg = (mst5 + mst13 + mst50) / 3.0

    df = load_index(index_for_cci)
    cci84 = float(cci(df, 84).iloc[-1]) if not df.empty else float("nan")
    cci_flex = _cci_to_flex(cci84)

    liq_s = float(liquidity_score(full_a_amt, 252).iloc[-1])
    liq_flex = _liq_to_flex(liq_s)

    flex = (mst_avg + cci_flex + liq_flex) / 3.0
    return {
        "score": round(flex, 1),
        "mst_avg": round(mst_avg, 1),
        "mst_5": round(mst5, 1),
        "mst_13": round(mst13, 1),
        "mst_50": round(mst50, 1),
        "cci84": round(cci84, 1) if not pd.isna(cci84) else None,
        "cci_state": classify_cci(cci84),
        "cci_flex": round(cci_flex, 1),
        "liquidity_score": round(liq_s, 1) if not pd.isna(liq_s) else None,
        "liquidity_band": liquidity_band(liq_s),
        "liq_flex": round(liq_flex, 1),
    }


def position_config(cycle_detail: pd.DataFrame | None = None) -> dict[str, Any]:
    """Config position from # strong sectors (SC30 ≥ 50)."""
    cyc = cycle_detail if cycle_detail is not None else cycle_detail_latest()
    if cyc.empty:
        return {"score": 0.0, "n_strong": 0, "n_hot": 0, "n_total": 0, "pct_strong": 0.0}
    n_total = len(cyc)
    sc30 = cyc["SC30"].dropna()
    n_strong = int((sc30 >= 50).sum())
    n_hot = int((sc30 >= 80).sum())
    pct_strong = n_strong / n_total if n_total else 0.0
    return {
        "score": _pct_strong_to_config(pct_strong),
        "n_strong": n_strong,
        "n_hot": n_hot,
        "n_total": n_total,
        "pct_strong": round(pct_strong * 100, 1),
    }


# ---------------------------------------------------------------------------
# Cycle phase + risk light (rule-based)
# ---------------------------------------------------------------------------

def market_cycle_phase(*, market_sc30: float, pct_strong: float, mst5: float,
                        liq_band: str, breadth_ratio: float) -> str:
    """Market-level cycle phase per distillation §17.

    Uses market_sc30 = RSV_30 of 万得全A, which is a broad-market index-level
    stochastic comparable to the original framework's SC30 中期.

    Phases: 酝酿 / 抱团 / 主流轮动 / 高潮 / 缩容 / 瓦解 / 下降趋势 / 中性
    """
    if pd.isna(market_sc30):
        return "n/a"
    if market_sc30 >= 80 and pct_strong >= 20 and breadth_ratio > 1.2:
        return "高潮"
    if market_sc30 >= 70 and pct_strong >= 25:
        return "抱团"
    if market_sc30 >= 55 and pct_strong >= 15:
        return "主流轮动"
    if market_sc30 < 30 and breadth_ratio < 0.5:
        return "瓦解"
    if liq_band == "匮乏" and mst5 < 40:
        return "缩容"
    if market_sc30 < 55 and breadth_ratio < 1.0:
        return "下降趋势"
    if pct_strong < 10 and market_sc30 < 50:
        return "酝酿"
    return "中性"


def market_state_label(temperature: float) -> str:
    """Map 0-100 temperature to a state label."""
    if pd.isna(temperature):
        return "n/a"
    if temperature >= 75:
        return "强势进攻"
    if temperature >= 55:
        return "偏多震荡"
    if temperature >= 35:
        return "偏空震荡"
    return "退潮防守"


def risk_light(*, temperature: float, cci84: float, mst5: float,
                liq_band: str) -> str:
    """Rule-based risk light. Historical-similarity scoring is deferred to
    the signal-backtest phase."""
    if pd.isna(temperature):
        return "n/a"
    # 红灯：严重超买，或温度低且广度差
    if (not pd.isna(cci84) and cci84 > 150) or (mst5 < 25 and temperature < 30):
        return "红"
    # 绿灯：温度足且非超买且广度OK且流动性非匮乏
    if (temperature >= 55 and (pd.isna(cci84) or cci84 < 120)
            and mst5 >= 45 and liq_band != "匮乏"):
        return "绿"
    return "黄"


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

@dataclass
class MarketStateSnapshot:
    date: str
    market_temperature: float
    market_state: str
    risk_light: str
    cycle_phase: str
    position_base: dict[str, Any]
    position_flex: dict[str, Any]
    position_config: dict[str, Any]
    breadth: dict[str, Any]
    source: str = "einvest.market_state"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def market_state_snapshot(
    *,
    weights: tuple[float, float, float] = (0.35, 0.35, 0.30),
    full_a: pd.DataFrame | None = None,
    close_panel: pd.DataFrame | None = None,
    cycle_detail: pd.DataFrame | None = None,
) -> MarketStateSnapshot | None:
    """Pull all components and synthesize a unified market state.

    `weights` applies to (position_base, position_flex, position_config) for the
    temperature composite. Defaults sum to 1.0.

    Pre-loaded params (all optional) let upper layers (e.g. Streamlit cache)
    share panels across modules instead of having each module read parquet
    independently.
    """
    if full_a is None:
        full_a = load_full_a()
    if full_a.empty:
        return None
    full_a_amt = full_a.set_index("date")["amt"]
    last_date = full_a["date"].iloc[-1].date().isoformat()

    if close_panel is None:
        close_panel = load_close_panel(universe())
    mst_df = mst(close_panel, windows=(5, 13, 50))
    udc = up_down_count(close_panel)
    cyc = cycle_detail if cycle_detail is not None else cycle_detail_latest()

    pb = position_base()
    pf = position_flex(full_a_amt=full_a_amt, mst_df=mst_df)
    pc = position_config(cycle_detail=cyc)

    w_base, w_flex, w_conf = weights
    temp = w_base * pb["score"] + w_flex * pf["score"] + w_conf * pc["score"]

    cci84 = pf["cci84"] if pf["cci84"] is not None else float("nan")
    mst5 = pf["mst_5"]
    liq_b = pf["liquidity_band"]
    breadth_ratio = float(udc["breadth_ratio"].iloc[-1])

    # Market-wide SC30/SC3 from 万得全A — comparable to original framework's SC30中期
    full_a_close = full_a.set_index("date")["close"]
    market_sc30 = float(rsv(full_a_close, 30).iloc[-1])
    market_sc3 = float(rsv(full_a_close, 3).iloc[-1])

    # Keep top_sc30 (per-concept max) for reference only
    top_sc30 = float(cyc["SC30"].max()) if not cyc.empty else float("nan")

    return MarketStateSnapshot(
        date=last_date,
        market_temperature=round(temp, 1),
        market_state=market_state_label(temp),
        risk_light=risk_light(
            temperature=temp,
            cci84=cci84,
            mst5=mst5,
            liq_band=liq_b,
        ),
        cycle_phase=market_cycle_phase(
            market_sc30=market_sc30,
            pct_strong=pc["pct_strong"],
            mst5=mst5,
            liq_band=liq_b,
            breadth_ratio=breadth_ratio,
        ),
        position_base=pb,
        position_flex=pf,
        position_config=pc,
        breadth={
            "up_count": int(udc["up_count"].iloc[-1]),
            "down_count": int(udc["down_count"].iloc[-1]),
            "flat_count": int(udc["flat_count"].iloc[-1]),
            "breadth_ratio": round(breadth_ratio, 2),
            "market_sc30": round(market_sc30, 1) if not pd.isna(market_sc30) else None,
            "market_sc3": round(market_sc3, 1) if not pd.isna(market_sc3) else None,
            "top_sc30": round(top_sc30, 1) if not pd.isna(top_sc30) else None,
        },
    )
