#!/usr/bin/env python3
from pathlib import Path
import json

from rudeus.science.known_material_cubic_llzo_joint_feasibility import (
    DIAGNOSTIC_VERSION,
    build_joint_occupancy_feasibility_diagnostics,
)

CIF = Path("data/benchmarks/known_material/structures/cod/7215448-r176453.cif")

def main() -> int:
    rows = build_joint_occupancy_feasibility_diagnostics(CIF)
    print(json.dumps({
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "diagnostic_only": True,
        "canonical_ensemble_changed": False,
        "constructive_not_exhaustive": True,
        "members": [row.to_dict() for row in rows],
    }, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
