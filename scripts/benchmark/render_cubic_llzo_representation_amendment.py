#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

from rudeus.science.known_material_cubic_llzo_policy_evidence import (
    build_cubic_llzo_fractional_occupancy_policy_evidence,
)
from rudeus.science.known_material_cubic_llzo_representation_amendment import (
    build_cubic_llzo_representation_amendment_candidate,
)

CIF = Path("data/benchmarks/known_material/structures/cod/7215448-r176453.cif")

def main() -> int:
    source_hash = hashlib.sha256(CIF.read_bytes()).hexdigest()
    _, old_execution, _ = build_cubic_llzo_fractional_occupancy_policy_evidence(
        CIF, source_artifact_hash=source_hash
    )
    candidate = build_cubic_llzo_representation_amendment_candidate(
        CIF,
        source_artifact_hash=source_hash,
        old_binding_hash=old_execution.visible_structure_hash,
    )
    payload = candidate.to_dict()
    payload["candidate_visible_structure_hash"] = candidate.candidate_binding.visible_structure_hash
    payload["binding_changed"] = (
        candidate.candidate_binding.visible_structure_hash != old_execution.visible_structure_hash
    )
    print(json.dumps(payload, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
