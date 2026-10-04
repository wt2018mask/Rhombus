import hashlib
import json
from pathlib import Path

import pytest

from rudeus.generation.m6b_reconciliation import write_selection_reconciliation


def test_reconciliation_binds_original_bytes_and_preserves_failure(tmp_path):
    from tests.test_m6b_generic_kaggle_contract import DRIVER, _valid_m6b_panel

    source_root = Path(__file__).resolve().parents[1] / "data/batches/audit"
    freeze_sha = hashlib.sha256((source_root / "candidate-supply-v2-version-9-observational-freeze-v1.json").read_bytes()).hexdigest()
    source_sha = hashlib.sha256((source_root / "g_candidate_supply_v2_mobile_ion_displace_diagnostic_panel.json").read_bytes()).hexdigest()
    report = tmp_path / "report.json"
    panel = tmp_path / "panel.json"
    prereg = tmp_path / "prereg.json"
    receipt = tmp_path / "receipt.json"
    panel_value = _valid_m6b_panel()
    del panel_value["metadata"]["ordered_cohort_identity"]
    panel_value["metadata"]["version_9_freeze_sha256"] = freeze_sha
    panel_value["metadata"]["version_9_panel_sha256"] = source_sha
    panel.write_text(json.dumps(panel_value), encoding="utf-8")
    report.write_text(json.dumps({
        "final_classification": "SCIENTIFIC_VALIDATION_FAIL",
        "config_identity": DRIVER.M6B_CONFIG_IDENTITY,
        "artifact": {"sha256": hashlib.sha256(panel.read_bytes()).hexdigest()},
        "validations": {
            "schema": True, "selection": False, "configuration": True,
            "authorization": True, "paired_identity_accounting": True,
            "source_identity": True, "raw_rows": True,
            "summary_reconciliation": True, "pass_identity": True,
            "failure": "M6-B validation failed: selection",
        },
        "protected_artifact_state_artifact": {"relative_path": "missing-original.json"},
    }), encoding="utf-8")
    selection = {
        "ordered_parent_ids": list(DRIVER.M6B_PARENT_IDS),
        "ordered_chemical_families": list(DRIVER.M6B_PARENT_FAMILIES),
        "rule": DRIVER.M6B_SELECTION_RULE,
        "excluded_m6a_parent_ids": list(DRIVER.M6A_PARENT_IDS),
        "source_freeze_sha256": freeze_sha,
        "source_panel_sha256": source_sha,
        "ordered_cohort_sha256": _valid_m6b_panel()["metadata"]["ordered_cohort_identity"],
    }
    prereg.write_text(json.dumps({"configuration_identity": DRIVER.M6B_CONFIG_IDENTITY,
                                  "parent_selection": selection}), encoding="utf-8")
    before = report.read_bytes()
    write_selection_reconciliation(report, panel, prereg, receipt)
    value = json.loads(receipt.read_bytes())
    assert value["selection_provenance_reconciled"] is True
    assert value["overall_provenance_pass"] is False
    assert value["original_remote_classification"] == "SCIENTIFIC_VALIDATION_FAIL"
    assert value["standalone_protected_state"] == "UNVERIFIED_BYTES_NOT_SUPPLIED"
    assert report.read_bytes() == before
    with pytest.raises(FileExistsError):
        write_selection_reconciliation(report, panel, prereg, receipt)
