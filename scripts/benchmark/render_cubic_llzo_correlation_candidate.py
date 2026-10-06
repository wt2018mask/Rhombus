#!/usr/bin/env python3
from pathlib import Path
import json

from rudeus.science.known_material_cubic_llzo_correlation_candidate import (
    build_correlation_aware_candidate_diagnostics,
)


CIF = Path("data/benchmarks/known_material/structures/cod/7215448-r176453.cif")


def main() -> int:
    rows = build_correlation_aware_candidate_diagnostics(CIF)
    payload = {
        "diagnostic_version": "known-material-cubic-llzo-correlation-aware-candidate-v1",
        "diagnostic_only": True,
        "canonical_ensemble_changed": False,
        "members": [row.to_dict() for row in rows],
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
