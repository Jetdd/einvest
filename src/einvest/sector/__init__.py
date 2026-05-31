"""Sector / concept module — industry-chain knowledge graph + quant overlay."""
from .chain import (
    CHAINS_DIR,
    available_chains,
    code6_to_rq,
    load_chain,
    parse_company,
)
from .chain_strength import chain_with_strength, segment_strength

__all__ = [
    "CHAINS_DIR",
    "available_chains",
    "code6_to_rq",
    "load_chain",
    "parse_company",
    "segment_strength",
    "chain_with_strength",
]
