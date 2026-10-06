import json
from pathlib import Path
import yaml

from rudeus.science.known_material_b5_p1_real_evidence import B5P1RealEvidenceBinding
from rudeus.science.known_material_b5_p2_execution_plan import build_b5_p2_execution_plan


def test_canonical_b5_p2_plan_contains_exact_p1_survivors():
    binding = B5P1RealEvidenceBinding.from_dict(json.loads(
        Path("data/benchmarks/known_material/b5_p1_real_evidence_v1.json").read_text()
    ))
    config = yaml.safe_load(Path("config.yaml").read_text())
    plan = build_b5_p2_execution_plan(binding, p2_protocol=config["p2"])
    assert len(plan.units) == 3
    assert {u.batch_id for u in plan.units} == {
        "df4431260652d2ea", "4ab81ca72174667c", "f47d66515f55ce3e"
    }
    assert plan.p2_protocol["temperature_K"] == 550.0
    assert plan.p2_protocol["equil_steps"] == 2000
    assert plan.p2_protocol["production_steps"] == 8000
    assert tuple(plan.p2_protocol["production_tier_schedule_provisional"]) == (1000, 3000, 8000)
    assert plan.planning_only is True
    assert plan.p2_tasks_created is False
    assert plan.qualification_evidence_authorized is False
