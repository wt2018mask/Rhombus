"""Metadata/byte-only negative tests. Synthetic files, no models or scores."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from rhombus.benchmark import tier_a_input_pin as pins
from rhombus.benchmark.tier_a_budget_contract import inspect_budget_draft
from rhombus.benchmark.tier_a_model_neb_preflight import (
    ARM_SOURCE_CATALOG, MACE_MEDIUM_SHA256, NEB_ILLUSTRATIVE_VALUES,
    inspect_offline_run_review, propose_shared_neb_numeric_candidate,
    verify_local_binary_bytes, verify_pilot_input_binding,
)
from test_tier_a_input_pin_and_local_meter_0204 import unpinned_draft, fake_zip


def synthetic_bound(tmp_path: Path, monkeypatch):
    d = unpinned_draft()
    monkeypatch.setattr(pins, "_verify_owner_zip", lambda p: None)
    path = tmp_path / "synthetic-only.zip"
    fake_zip(path, [e["edge_id"] for e in d["edges"]])
    return pins.pin_train_initial_xyz_bytes(d, path)


def test_original_pinned_inputs_validate_without_rereading_archive(tmp_path, monkeypatch):
    draft, receipt = synthetic_bound(tmp_path, monkeypatch)
    result = verify_pilot_input_binding(draft, receipt)
    assert result["verified_unchanged_identity_rows"] == 4
    assert result["verified_uncompressed_bytes"] > 0
    review = inspect_offline_run_review(draft=draft, input_binding_receipt=receipt)
    assert review["execution_authorized"] is False
    assert review["benchmark_status"] == "BENCHMARK_NOT_FROZEN"
    assert review["pilot_paired_rows_required"] == 8
    assert review["eligible_for_separate_owner_review"] is False
    assert "NEB_NUMERIC_SETTINGS_MISSING" in review["preflight_blockers"]
    assert "MODEL_CHECKPOINT_UNPINNED" in review["preflight_blockers"]
    assert review["input_binding"]["publisher_identity"] == "OWNER_PROVIDED_UNATTESTED"
    assert review["heldout_targets_read"] is False
    assert review["calculation_performed"] is False


@pytest.mark.parametrize("mutate,pattern", [
    (lambda r: r.update(archive_owner_sha256="0"*64), "PROVENANCE_CONTRADICTION"),
    (lambda r: r.update(publisher_authenticity="SIGNED_BY_PUBLISHER"), "PROVENANCE_CONTRADICTION"),
    (lambda r: r.update(target_columns_access="DECODED"), "PROVENANCE_CONTRADICTION"),
    (lambda r: r.update(relaxed_dft_xyz_access="INSPECTED"), "PROVENANCE_CONTRADICTION"),
    (lambda r: r.update(execution_authorized=True), "PROVENANCE_CONTRADICTION"),
    (lambda r: r["identities"][0].update(raw_uncompressed_sha256="f"*64), "HASH_OR_GROUP_MISMATCH"),
    (lambda r: r["identities"][0].update(group_id="CHEMSYS:OTHER"), "HASH_OR_GROUP_MISMATCH"),
    (lambda r: r["identities"][0].update(zip_member="bad-path"), "HASH_OR_GROUP_MISMATCH"),
    (lambda r: r.update(initial_member_count=3), "RECEIPT_INVALID"),
    (lambda r: r["identities"].append(deepcopy(r["identities"][0])), "RECEIPT_INVALID"),
    (lambda r: r.update(em_dft=1.0), "EXACT_FIELDS"),
])
def test_wrong_input_receipt_fails_closed(tmp_path, monkeypatch, mutate, pattern):
    draft, receipt = synthetic_bound(tmp_path, monkeypatch)
    mutate(receipt)
    with pytest.raises(ValueError, match=pattern):
        verify_pilot_input_binding(draft, receipt)


def test_changed_pinned_edge_fails_closed(tmp_path, monkeypatch):
    d, receipt = synthetic_bound(tmp_path, monkeypatch)
    d["edges"][0]["initial_images_sha256"] = "0"*64
    with pytest.raises(ValueError, match="HASH_OR_GROUP_MISMATCH"):
        verify_pilot_input_binding(d, receipt)


def test_numeric_neb_proposal_remains_unfrozen(tmp_path, monkeypatch):
    d, r = synthetic_bound(tmp_path, monkeypatch)
    suggestion = propose_shared_neb_numeric_candidate(d)
    assert d["neb"]["neb_fmax_ev_ang"] is None
    assert all(suggestion["neb"][k] == v for k, v in NEB_ILLUSTRATIVE_VALUES.items())
    assert suggestion["execution_authorized"] is False
    assert "PER_ARM_PER_EDGE_CAPS_MISSING" in inspect_budget_draft(suggestion)["blockers"]
    assert verify_pilot_input_binding(suggestion, r)["verified_unchanged_identity_rows"] == 4
    suggestion["neb"]["neb_fmax_ev_ang"] = .2
    with pytest.raises(ValueError, match="EXISTING_NEB_SETTING_REQUIRES_SEPARATE_REVIEW"):
        propose_shared_neb_numeric_candidate(suggestion)


def test_local_byte_only_hashing_never_loads_model(tmp_path):
    p = tmp_path / "synthetic-not-a-real-model.bin"
    raw = b"arbitrary inert bytes\x00\x01"
    p.write_bytes(raw)
    hash_ = sha256(raw).hexdigest()
    r = verify_local_binary_bytes(p, expected_sha256=hash_, expected_size_bytes=len(raw))
    assert r["verification"] == "MATCHED_DECLARED_SHA256_AND_SIZE"
    assert r["model_deserialized"] is False and r["model_inference_executed"] is False
    assert r["size_bytes"] == len(raw)
    unpinned = verify_local_binary_bytes(p)
    assert unpinned["verification"] == "OBSERVED_BYTES_ONLY_NOT_PINNED"


def test_binary_incorrect_hash_size_type_and_symlink(tmp_path):
    p = tmp_path / "fake.model"
    p.write_bytes(b"fake")
    with pytest.raises(ValueError, match="MODEL_SHA256_MISMATCH"):
        verify_local_binary_bytes(p, expected_sha256="0"*64)
    with pytest.raises(ValueError, match="MODEL_SIZE_MISMATCH"):
        verify_local_binary_bytes(p, expected_size_bytes=100)
    with pytest.raises(ValueError, match="INVALID_EXPECTED_MODEL_SIZE"):
        verify_local_binary_bytes(p, expected_size_bytes=True)
    with pytest.raises(ValueError, match="SHA256_REQUIRED"):
        verify_local_binary_bytes(p, expected_sha256="bad")
    with pytest.raises(ValueError, match="MODEL_FILE_NOT_ACCESSIBLE"):
        verify_local_binary_bytes(tmp_path / "not-exists")
    sym = tmp_path / "alias.model"
    try:
        sym.symlink_to(p)
    except (OSError, NotImplementedError):
        pass
    else:
        with pytest.raises(ValueError, match="MODEL_SYMLINK_NOT_ACCEPTED"):
            verify_local_binary_bytes(sym)


def test_small_model_observed_but_not_misrepresented_as_pinned(tmp_path, monkeypatch):
    d, receipt = synthetic_bound(tmp_path, monkeypatch)
    p = tmp_path / "synthetic-small-model.bin"
    p.write_bytes(b"NOT MACE, ONLY A TEST")
    result = inspect_offline_run_review(
        draft=d, input_binding_receipt=receipt,
        model_files={"MACE_MP_0_SMALL_PUBLISHER_EXAMPLE": p})
    m = result["models"]["MACE_MP_0_SMALL_PUBLISHER_EXAMPLE"]
    assert m["file_status"] == "OBSERVED_UNPINNED"
    assert m["byte_observation"]["model_deserialized"] is False
    assert "MACE_MP_0_SMALL_PUBLISHER_EXAMPLE:CHECKPOINT_REQUIRES_OWNER_PIN" in result["preflight_blockers"]
    assert result["eligible_for_separate_owner_review"] is False
    assert result["models"]["MACE_MPA_0_MEDIUM_RHOMBUS"]["file_status"] == "NOT_PROVIDED"


def test_medium_wrong_checkpoint_size_rejected_and_not_substituted(tmp_path, monkeypatch):
    d, receipt = synthetic_bound(tmp_path, monkeypatch)
    p = tmp_path / "not-medium.model"
    p.write_bytes(b"fake")
    out = inspect_offline_run_review(draft=d, input_binding_receipt=receipt,
                                     model_files={"MACE_MPA_0_MEDIUM_RHOMBUS": p})
    assert out["models"]["MACE_MPA_0_MEDIUM_RHOMBUS"]["file_status"] == "REJECTED"
    assert out["models"]["MACE_MPA_0_MEDIUM_RHOMBUS"]["failure_code"] == "MODEL_SIZE_MISMATCH"
    assert out["execution_authorized"] is False
    assert d["model_arms"][1]["checkpoint_sha256"] == MACE_MEDIUM_SHA256


def test_runtime_claims_are_not_independently_attested(tmp_path, monkeypatch):
    d, r = synthetic_bound(tmp_path, monkeypatch)
    runtime = {
        "python_version": "3.11", "ase_version": "3.26", "mace_torch_version": "0.3.16",
        "torch_version": "2.4.1", "numpy_version": "1.26.4",
        "mace_source_commit": "a"*40, "calculator_adapter_sha256": "b"*64,
        "calculator_call_accounting": "CALCULATOR_CALLBACK_INSTRUMENTED",
        "thread_control_evidence": "CPU_2_THREADS_PER_ARM_SEQUENTIAL",
    }
    result = inspect_offline_run_review(draft=d, input_binding_receipt=r,
                                        runtime_declaration=runtime)
    assert result["runtime"]["declaration_status"] == "OWNER_DECLARED_NOT_INDEPENDENT_RUNTIME_ATTESTED"
    assert "RUNTIME_DECLARATION_NOT_INDEPENDENT_ATTESTATION" in result["preflight_blockers"]
    runtime["calculator_call_accounting"] = "COUNTS_ESTIMATED_NOT_OBSERVED"
    with pytest.raises(ValueError, match="CALL_COUNTS_NOT_ATTESTED_BY_DECLARATION"):
        inspect_offline_run_review(draft=d, input_binding_receipt=r,
                                   runtime_declaration=runtime)


def test_model_arms_cannot_be_unknown_and_source_url_is_explicit(tmp_path, monkeypatch):
    d, receipt = synthetic_bound(tmp_path, monkeypatch)
    assert ARM_SOURCE_CATALOG["MACE_MP_0_SMALL_PUBLISHER_EXAMPLE"]["source_url"].startswith("https://github.com/ACEsuit/mace-mp/")
    with pytest.raises(ValueError, match="UNKNOWN_MODEL_ARM_FILE"):
        inspect_offline_run_review(draft=d, input_binding_receipt=receipt,
                                   model_files={"other": tmp_path / "file"})


def test_cli_generates_read_only_report_and_suggestion_without_overwrite(tmp_path, monkeypatch, capsys):
    from scripts.benchmark.inspect_tier_a_model_neb_0204 import main
    d, receipt = synthetic_bound(tmp_path, monkeypatch)
    draft_path, binding_path = tmp_path / "draft.json", tmp_path / "receipt.json"
    draft_path.write_text(json.dumps(d), encoding="utf-8")
    binding_path.write_text(json.dumps(receipt), encoding="utf-8")
    report_path = tmp_path / "review.json"
    args = ["--draft", str(draft_path), "--binding-receipt", str(binding_path),
            "--output", str(report_path), "--candidate-neb-settings"]
    report = main(args)
    assert report["execution_authorized"] is False
    suggestion_path = tmp_path / "review_SUGGESTED_NEB_NOT_FROZEN.json"
    assert suggestion_path.is_file()
    assert json.loads(report_path.read_text())["heldout_targets_read"] is False
    with pytest.raises(FileExistsError):
        main(args)


def test_cli_rejects_target_contamination_and_duplicate_json(tmp_path, monkeypatch):
    from scripts.benchmark.inspect_tier_a_model_neb_0204 import main
    d, receipt = synthetic_bound(tmp_path, monkeypatch)
    draft_path, binding_path = tmp_path / "draft.json", tmp_path / "receipt.json"
    draft_path.write_text(json.dumps(d), encoding="utf-8")
    binding_path.write_text(json.dumps(receipt), encoding="utf-8")
    d["em_dft"] = 0.1
    draft_path.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ValueError, match="EXACT_FIELDS"):
        main(["--draft", str(draft_path), "--binding-receipt", str(binding_path),
              "--output", str(tmp_path / "out.json")])
    draft_path.write_text('{"a":1,"a":2}', encoding="utf-8")
    with pytest.raises(ValueError, match="DUPLICATE_JSON_KEY"):
        main(["--draft", str(draft_path), "--binding-receipt", str(binding_path),
              "--output", str(tmp_path / "out.json")])
