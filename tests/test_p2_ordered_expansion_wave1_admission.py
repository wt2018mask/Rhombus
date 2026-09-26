"""Admission contract for ordered-expansion wave1 P2 GPU worker."""

import json
from pathlib import Path

from rudeus.mlip.p2 import (
    P2_PROTOCOL_DEFAULTS,
    P2_PROTOCOL_VERSION,
    load_authorization_manifest,
)

P1_DONE = Path("data/batches/done_ordered_expansion_wave1_v1")
AUTH = Path("data/batches/audit/p2_ordered_expansion_wave1_v1_authorized.json")
EXPECTED_IDENTITY = "b21faafbbad50910d61ca9a8a695b3cddddd3fce8a8f7cf3d6bd5ce936e75200"


def test_ordered_expansion_wave1_p2_gpu_admission_contract():
    manifest = json.loads(AUTH.read_text(encoding="utf-8"))

    assert manifest["expected_authorized"] == 33
    assert manifest["verified_eligible"] == 33
    assert manifest["decision"]["verdict"] == "AUTHORIZED"
    assert manifest["decision"]["md_executions"] == 0
    assert manifest["cohort_identity_sha256"] == EXPECTED_IDENTITY
    assert len(manifest["candidates"]) == 33
    assert len({row["batch_id"] for row in manifest["candidates"]}) == 33
    assert all(row["p0_state"] == "PLAUSIBLE" for row in manifest["candidates"])
    assert all(row["p1_verdict"] == "KEEP_FOR_P2" for row in manifest["candidates"])

    ids = load_authorization_manifest(AUTH, P1_DONE)
    assert len(ids) == 33

    assert P2_PROTOCOL_VERSION == "p2-adaptive-v2-fixcom-constraint-provisional"
    assert P2_PROTOCOL_DEFAULTS["p2_protocol_version"] == P2_PROTOCOL_VERSION
    assert P2_PROTOCOL_DEFAULTS["temperature_K"] == 550.0
    assert P2_PROTOCOL_DEFAULTS["equil_steps"] == 2000
    assert P2_PROTOCOL_DEFAULTS["production_steps"] == 8000
    assert P2_PROTOCOL_DEFAULTS["sample_interval_steps"] == 10
    assert P2_PROTOCOL_DEFAULTS["fix_center_of_mass"] is True
