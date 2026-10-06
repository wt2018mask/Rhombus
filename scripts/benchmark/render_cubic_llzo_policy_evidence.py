"""Render the canonical cubic Al-LLZO B4 policy-evidence candidate.

This command is intentionally non-mutating.  It lets CI expose the exact
content-addressed strategy/evidence/execution hashes before those values are
written into canonical benchmark ledgers.
"""
from __future__ import annotations

import json
from pathlib import Path

from rudeus.science.known_material_cubic_llzo_policy_evidence import (
    build_cubic_llzo_fractional_occupancy_policy_evidence,
)


ROOT = Path("data/benchmarks/known_material")
CIF = ROOT / "structures/cod/7215448-r176453.cif"
SOURCE_HASH = "db5f259f418edca7111136c0bc3a48b7f7cccde87411d54c48ebf71821217eec"


def render() -> dict:
    strategy, execution, entry = (
        build_cubic_llzo_fractional_occupancy_policy_evidence(
            CIF,
            source_artifact_hash=SOURCE_HASH,
        )
    )
    return {
        "source_artifact_hash": SOURCE_HASH,
        "strategy_hash": strategy.content_hash,
        "strategy": strategy.to_dict(),
        "execution_structure_hash": execution.visible_structure_hash,
        "execution_binding_hash": execution.content_hash,
        "execution": execution.to_dict(),
        "representation_evidence_hash": entry.content_hash,
        "representation_evidence": entry.to_dict(),
    }


def main() -> None:
    print(json.dumps(render(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
