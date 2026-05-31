"""Load + parse concept industry-chain YAML files.

One file per concept at ``config/concept_chains/{name}.yaml`` (see
``doc/sector_module_design.md`` for the schema). Companies are written as
``"名称:代码"`` where 代码 is the 6-digit A-share number.
"""
from __future__ import annotations

import functools
from pathlib import Path

import yaml

from ..config import PROJECT_ROOT

CHAINS_DIR = PROJECT_ROOT / "config" / "concept_chains"


def code6_to_rq(code: str) -> str:
    """6-digit A-share code → rqdatac order_book_id.

    6/9-prefixed → Shanghai (.XSHG); everything else (0/3) → Shenzhen (.XSHE).
    """
    c = code.strip()
    if "." in c:  # already an rq / wind code
        body, _, suf = c.partition(".")
        return f"{body}.XSHG" if suf.upper() in {"SH", "XSHG"} else f"{body}.XSHE"
    return f"{c}.XSHG" if c[:1] in {"6", "9"} else f"{c}.XSHE"


def parse_company(s: str) -> tuple[str, str]:
    """``"中际旭创:300308"`` → ``("中际旭创", "300308.XSHE")``."""
    name, _, code = s.partition(":")
    return name.strip(), code6_to_rq(code.strip())


@functools.cache
def _index() -> dict[str, Path]:
    """Map concept name (and aliases) → yaml path."""
    out: dict[str, Path] = {}
    if not CHAINS_DIR.exists():
        return out
    for p in sorted(CHAINS_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        concept = data.get("concept")
        if concept:
            out[str(concept)] = p
        for a in data.get("aliases", []) or []:
            out.setdefault(str(a), p)
    return out


def clear_chain_cache() -> None:
    _index.cache_clear()
    load_chain.cache_clear()


def available_chains() -> list[str]:
    """Concept names that currently have a chain file (primary names only)."""
    seen: list[str] = []
    if not CHAINS_DIR.exists():
        return seen
    for p in sorted(CHAINS_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        c = data.get("concept")
        if c:
            seen.append(str(c))
    return seen


@functools.cache
def load_chain(concept: str) -> dict | None:
    """Return the parsed chain dict for a concept (or alias), else None.

    Each segment gains a ``companies_parsed`` list of (name, rq_code) tuples.
    """
    path = _index().get(concept)
    if path is None:
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for tier, segments in (data.get("chain") or {}).items():
        for seg in segments or []:
            seg["companies_parsed"] = [parse_company(c) for c in seg.get("companies", [])]
    return data
