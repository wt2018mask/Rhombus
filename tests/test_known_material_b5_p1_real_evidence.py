import json
from pathlib import Path

from rudeus.science.known_material_b5_p1_real_evidence import (
    B5P1RealEvidenceBinding,
    build_p2_authorization_rows,
)


def test_canonical_real_p1_evidence_binds_exact_three_p2_survivors():
    payload = json.loads(
        Path("data/benchmarks/known_material/b5_p1_real_evidence_v1.json").read_text()
    )
    binding = B5P1RealEvidenceBinding.from_dict(payload)
    rows = build_p2_authorization_rows(binding)
    assert len(rows) == 3
    assert {row["batch_id"] for row in rows} == {
        "df4431260652d2ea", "4ab81ca72174667c", "f47d66515f55ce3e"
    }
    assert binding.operational_error_count == 0
    assert binding.qualification_evidence_authorized is False
