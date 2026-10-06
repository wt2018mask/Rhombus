#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

from rudeus.science.known_material_cubic_llzo_formal_amendment_proposal import (
    FORMAL_AMENDMENT_PROPOSAL_VERSION,
    build_cubic_llzo_formal_amendment_proposal,
)

CIF = Path("data/benchmarks/known_material/structures/cod/7215448-r176453.cif")

def main() -> int:
    source_hash = hashlib.sha256(CIF.read_bytes()).hexdigest()
    candidate, strategy, execution, entry = build_cubic_llzo_formal_amendment_proposal(
        CIF, source_artifact_hash=source_hash
    )
    print(json.dumps({
        "proposal_version": FORMAL_AMENDMENT_PROPOSAL_VERSION,
        "diagnostic_only": True,
        "persisted_contracts_mutated": False,
        "source_artifact_hash": source_hash,
        "candidate_hash": candidate.content_hash,
        "strategy_hash": strategy.content_hash,
        "execution_structure_hash": execution.visible_structure_hash,
        "representation_evidence_entry": entry.to_dict(),
        "representation_evidence_entry_hash": entry.content_hash,
    }, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
