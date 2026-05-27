"""Code-format converters between Wind and rqdatac conventions.

Wind:      000001.SZ   600000.SH   688981.SH   831010.BJ
rqdatac:   000001.XSHE 600000.XSHG 688981.XSHG 831010.NEEQ

Indices:   8841388.WI  (Wind-only)        ;  000300.XSHG (rqdatac CSI300)
"""
from __future__ import annotations

from typing import Iterable


_WIND_TO_RQ = {"SZ": "XSHE", "SH": "XSHG", "BJ": "NEEQ"}
_RQ_TO_WIND = {v: k for k, v in _WIND_TO_RQ.items()}


def wind_to_rq(code: str) -> str:
    """000001.SZ → 000001.XSHE."""
    if "." not in code:
        return code
    body, suffix = code.rsplit(".", 1)
    return f"{body}.{_WIND_TO_RQ.get(suffix.upper(), suffix)}"


def rq_to_wind(code: str) -> str:
    """000001.XSHE → 000001.SZ."""
    if "." not in code:
        return code
    body, suffix = code.rsplit(".", 1)
    return f"{body}.{_RQ_TO_WIND.get(suffix.upper(), suffix)}"


def wind_to_rq_many(codes: Iterable[str]) -> list[str]:
    return [wind_to_rq(c) for c in codes]


def rq_to_wind_many(codes: Iterable[str]) -> list[str]:
    return [rq_to_wind(c) for c in codes]
