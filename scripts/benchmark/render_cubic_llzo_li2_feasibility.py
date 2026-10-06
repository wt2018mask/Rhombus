#!/usr/bin/env python3
"""Render cubic Al-LLZO Li2 correlation feasibility diagnostic."""
from pathlib import Path
import json

from rudeus.science.known_material_cubic_llzo_li2_feasibility import (
    build_cubic_llzo_li2_correlation_feasibility,
)


CIF = Path("data/benchmarks/known_material/structures/cod/7215448-r176453.cif")


def main() -> int:
    result = build_cubic_llzo_li2_correlation_feasibility(CIF)
    payload = result.to_dict()
    payload["diagnostic_only"] = True
    payload["representation_change_authorized"] = False
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
