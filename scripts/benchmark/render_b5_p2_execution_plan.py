#!/usr/bin/env python3
import json
from pathlib import Path

import yaml

from rudeus.science.known_material_b5_p1_real_evidence import B5P1RealEvidenceBinding
from rudeus.science.known_material_b5_p2_execution_plan import build_b5_p2_execution_plan


def main() -> int:
    binding = B5P1RealEvidenceBinding.from_dict(json.loads(
        Path("data/benchmarks/known_material/b5_p1_real_evidence_v1.json").read_text()
    ))
    config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
    plan = build_b5_p2_execution_plan(binding, p2_protocol=config["p2"])
    print(json.dumps(plan.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
