"""No-network contracts for manual, opt-in frozen WBM v2 profiling."""
from __future__ import annotations
import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/phase3-wbm-v2-original-profile-manual.yml"
REGISTRY = ROOT / "data/development/phase3_wbm_file_freeze_v1.json"


def _workflow():
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_only_manual_opt_in_can_launch_original_wbm_transfer():
    w = _workflow()
    assert set(w["on"]) == {"workflow_dispatch"}
    inputs = w["on"]["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"run_verified_profile"}
    assert inputs["run_verified_profile"]["type"] == "boolean"
    assert inputs["run_verified_profile"]["default"] == "false"
    job = w["jobs"]["verified-original-profile"]
    assert "inputs.run_verified_profile == true" in job["if"]
    assert int(job["timeout-minutes"]) <= 40
    assert w["permissions"] == {"contents": "read"}


def test_remote_source_url_matches_frozen_matbench_registry():
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    src = next(row for row in reg["files"] if row["file_id"] == "wbm_initial_structures")
    assert src["url"] == "https://figshare.com/files/53161835"
    assert src["expected_md5"] == "b809f101dd42a745ec2baabe7eb16f11"
    job = _workflow()["jobs"]["verified-original-profile"]
    download = next(step for step in job["steps"] if "Download one original WBM" in step["name"])
    cmd = download["run"]
    assert "https://figshare.com/ndownloader/files/53161835" in cmd
    assert "--max-filesize 2147483648" in cmd
    assert "--max-time 1200" in cmd
    assert src["expected_md5"] in cmd
    assert "98d545172c1ea9060f03f40cace6f8173a4ac06f1ee875ccd963765211519b58" in cmd
    assert "md5sum --check" in cmd and "sha256sum --check" in cmd


def test_no_raw_wbm_bytes_are_uploaded_even_if_profile_fails():
    job = _workflow()["jobs"]["verified-original-profile"]
    steps = job["steps"]
    upload = [x for x in steps if str(x.get("uses", "")).startswith("actions/upload-artifact@")]
    assert len(upload) == 1
    assert upload[0]["with"]["path"] == (
        "${{ runner.temp }}/wbm-v2-original-source-profile.json"
    )
    assert upload[0]["with"]["if-no-files-found"] == "error"
    assert int(upload[0]["with"]["retention-days"]) <= 7
    cleanup = next(x for x in steps if "Delete original data" in x["name"])
    assert cleanup["if"] == "always()"
    assert "rm -f" in cleanup["run"]
    assert "wbm-original-init-structs.jsonl.gz" in cleanup["run"]


def test_original_verification_precedes_structure_parsing_and_upload():
    steps = _workflow()["jobs"]["verified-original-profile"]["steps"]
    names = [x["name"] for x in steps]
    assert names.index("Download one original WBM gzip and prove frozen MD5 and SHA256") < (
        names.index("Derive v2 structure candidate distribution from verified original")
    )
    assert names.index("Derive v2 structure candidate distribution from verified original") < (
        names.index("Independently verify JSON-only evidence policy before upload")
    )
    assert names.index("Independently verify JSON-only evidence policy before upload") < (
        names.index("Upload verified source-profile metadata only")
    )
    cmds = "\n".join(str(s.get("run", "")) for s in steps)
    assert "profile_wbm_v2_original_source" in cmds
    assert '"wbm_initial_structure_count"] == WBM_COUNT' in cmds
    assert "unseen_generalization_authorized" in cmds
    assert "full_source_transfer_authorized" in cmds


def test_manual_job_has_no_write_token_or_persisted_checkout_credentials():
    wf = _workflow()
    steps = wf["jobs"]["verified-original-profile"]["steps"]
    checkout = steps[0]
    assert checkout["with"]["ref"] == "${{ github.sha }}"
    assert checkout["with"]["persist-credentials"] == "false"
    source = WORKFLOW.read_text(encoding="utf-8")
    for prohibited in ("secrets.", "contents: write", "pull_request:", "push:", "schedule:", "repository_dispatch:", "kaggle "):
        assert prohibited not in source


def test_frozen_composition_protocol_and_no_training_claim():
    from rhombus.domain.mptrj_source_overlap import WBM_COUNT, WBM_SHA256
    from rhombus.domain.structure_protocols import CANDIDATE_FINGERPRINT_PROTOCOL_ID
    assert WBM_COUNT == 256_963
    assert WBM_SHA256 == "98d545172c1ea9060f03f40cace6f8173a4ac06f1ee875ccd963765211519b58"
    assert CANDIDATE_FINGERPRINT_PROTOCOL_ID == (
        "rhombus-reduced-composition-candidate-fingerprint-v2"
    )
