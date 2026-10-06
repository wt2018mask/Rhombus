#!/usr/bin/env python3
"""Render cubic Al-LLZO B5 raw-P0 diagnostics as canonical JSON."""
from pathlib import Path
import json

from rudeus.science.known_material_cubic_llzo_p0_diagnostic import (
    build_cubic_llzo_p0_diagnostics,
)


CIF = Path("data/benchmarks/known_material/structures/cod/7215448-r176453.cif")


def main() -> int:
    diagnostics = build_cubic_llzo_p0_diagnostics(CIF)
    payload = {
        "diagnostic_version": "known-material-cubic-llzo-p0-diagnostic-v1",
        "diagnostic_only": True,
        "material_verdict_authorized": False,
        "members": [item.to_dict() for item in diagnostics],
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
