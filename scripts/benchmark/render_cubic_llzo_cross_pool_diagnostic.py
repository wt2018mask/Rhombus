#!/usr/bin/env python3
from pathlib import Path
import json

from rudeus.science.known_material_cubic_llzo_cross_pool_diagnostic import (
    build_cross_pool_clash_diagnostics,
)

CIF = Path("data/benchmarks/known_material/structures/cod/7215448-r176453.cif")

def main() -> int:
    rows = build_cross_pool_clash_diagnostics(CIF)
    print(json.dumps({
        "diagnostic_version": "known-material-cubic-llzo-cross-pool-clash-diagnostic-v1",
        "diagnostic_only": True,
        "members": [row.to_dict() for row in rows],
    }, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
