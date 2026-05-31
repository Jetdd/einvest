"""Validate concept-chain YAML files.

Checks:
  - YAML parses and has a concept.
  - concept exists in HOT_CONCEPTS.
  - poster path exists when provided.
  - company entries parse as "name:code".
  - structured chain companies belong to that concept's Wind constituents.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from einvest.io import constituents  # noqa: E402
from einvest.sector import CHAINS_DIR, parse_company  # noqa: E402
from einvest.sectors import all_concepts  # noqa: E402


def iter_chain_files() -> list[Path]:
    return sorted(CHAINS_DIR.glob("*.yaml")) if CHAINS_DIR.exists() else []


def validate(*, verbose: bool = False) -> int:
    hot = set(all_concepts())
    errors: list[str] = []
    structured = 0
    poster_only = 0

    for path in iter_chain_files():
        rel = path.relative_to(ROOT)
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            errors.append(f"{rel}: YAML parse failed: {exc}")
            continue

        concept = data.get("concept")
        if not concept:
            errors.append(f"{rel}: missing concept")
            continue
        if concept not in hot:
            errors.append(f"{rel}: concept not in HOT_CONCEPTS: {concept}")

        poster = data.get("poster")
        if poster and not (ROOT / poster).exists():
            errors.append(f"{rel}: poster does not exist: {poster}")

        chain = data.get("chain") or {}
        if chain:
            structured += 1
        else:
            poster_only += 1
            continue

        allowed = set(constituents(concept))
        for tier, segments in chain.items():
            if not isinstance(segments, list):
                errors.append(f"{rel}: chain.{tier} must be a list")
                continue
            for seg in segments:
                segment = seg.get("segment", "<missing segment>")
                companies = seg.get("companies") or []
                if not companies:
                    errors.append(f"{rel}: {tier}/{segment} has no companies")
                for item in companies:
                    try:
                        name, rq_code = parse_company(str(item))
                    except Exception as exc:
                        errors.append(f"{rel}: bad company entry {item!r}: {exc}")
                        continue
                    if rq_code not in allowed:
                        errors.append(
                            f"{rel}: {tier}/{segment}: {name}:{rq_code} "
                            f"not in concept constituents"
                        )

        if verbose:
            print(f"[ok] {concept}: {sum(len(v or []) for v in chain.values())} segments")

    print(
        f"files={len(iter_chain_files())} structured={structured} "
        f"poster_only={poster_only} errors={len(errors)}"
    )
    for err in errors:
        print(f"[error] {err}")
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    return validate(verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
