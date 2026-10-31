"""Adversarial supply-chain tests. NO real MACE files, inference, or targets."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from rhombus.benchmark import tier_a_checkpoint_supply as m
from rhombus.benchmark.tier_a_model_neb_preflight import verify_local_binary_bytes
from test_tier_a_input_pin_and_local_meter_0204 import unpinned_draft


def test_upstream_release_identity_and_third_party_checksum_distinct():
    assert m.ASSET_INVENTORY[m.SMALL_ID]["size_bytes"] == 32_581_838
    assert m.ASSET_INVENTORY[m.MEDIUM_ID]["size_bytes"] == 79_462_305
    assert m.ASSET_INVENTORY[m.SMALL_ID]["asset_id"] == 145_021_750
    assert m.ASSET_INVENTORY[m.MEDIUM_ID]["asset_id"] == 213_937_064
    assert m.SMALL_THIRD_PARTY_SHA256 != m.MACE_MEDIUM_SHA256
    assert all(x["release_asset_sha256"] is None for x in m.ASSET_INVENTORY.values())


def test_metadata_only_creates_non_executable_unfrozen_report():
    d = unpinned_draft()
    review = m.inspect_supply(d)
    assert review["execution_authorized"] is False
    assert review["benchmark_status"] == "BENCHMARK_NOT_FROZEN"
    assert review["model_loads"] is False
    assert review["model_evaluations"] == 0
    assert review["heldout_targets_read"] is False
    assert "LOCAL_FILE_NOT_VERIFIED" in " ".join(review["supply_blockers"])
    assert review["model_arms"][m.SMALL_ID]["reference_sha256"] == m.SMALL_THIRD_PARTY_SHA256
    assert review["model_arms"][m.SMALL_ID]["draft_sha256"] is None
    assert d["model_arms"][0]["checkpoint_sha256"] is None
    assert review == m.inspect_supply(d)


def test_unknown_arm_and_bad_draft_fail_closed(tmp_path):
    d = unpinned_draft()
    with pytest.raises(ValueError, match="UNKNOWN_MODEL_ROLE"):
        m.inspect_supply(d, provided_files={"UNKNOWN": tmp_path / "x"})
    with pytest.raises(ValueError, match="UNKNOWN_MODEL_ROLE"):
        m.inspect_supply(d, provided_files=[tmp_path / "x"])
    d["em_dft"] = 0.42
    with pytest.raises(ValueError, match="EXACT_FIELDS"):
        m.inspect_supply(d)


def test_declared_small_digest_conflict_is_detected():
    d = unpinned_draft()
    d["model_arms"][0]["checkpoint_sha256"] = "a" * 64
    r = m.inspect_supply(d)
    assert any("DRAFT_DIGEST_CONFLICTS_WITH_REFERENCE" in x for x in r["supply_blockers"])
    assert r["execution_authorized"] is False


def test_small_fake_binary_rejected_without_loading(tmp_path):
    fake = tmp_path / "not-a-checkpoint.model"
    fake.write_bytes(b"SYNTHETIC NOT A REAL MODEL")
    r = m.inspect_supply(unpinned_draft(), provided_files={m.SMALL_ID: fake})
    assert r["model_arms"][m.SMALL_ID]["local_file_status"] == "REJECTED"
    assert r["model_arms"][m.SMALL_ID]["rejection_code"] == "MODEL_SIZE_MISMATCH"
    assert any("LOCAL_BYTES_REJECTED" in x for x in r["supply_blockers"])
    assert r["execution_authorized"] is False


def test_medium_fake_binary_rejected_without_loading(tmp_path):
    fake = tmp_path / "fake-medium.model"
    fake.write_bytes(b"fake")
    r = m.inspect_supply(unpinned_draft(), provided_files={m.MEDIUM_ID: fake})
    assert r["model_arms"][m.MEDIUM_ID]["rejection_code"] == "MODEL_SIZE_MISMATCH"
    assert r["model_arms"][m.SMALL_ID]["local_file_status"] == "NOT_PROVIDED"


def test_symlink_asset_rejected(tmp_path):
    p = tmp_path / "real"; p.write_bytes(b"fake")
    s = tmp_path / "link"
    s.symlink_to(p)
    r = m.inspect_supply(unpinned_draft(), provided_files={m.SMALL_ID: s})
    assert r["model_arms"][m.SMALL_ID]["rejection_code"] == "MODEL_SYMLINK_NOT_ACCEPTED"


def test_candidate_pin_refuses_missing_or_forged_receipt(tmp_path):
    d = unpinned_draft()
    r = m.inspect_supply(d)
    with pytest.raises(ValueError, match="SMALL_MODEL_BYTES_MUST_BE_VERIFIED"):
        m.make_small_digest_candidate(d, r, small_model_file=tmp_path / "no")
    forged = deepcopy(r)
    forged["model_arms"][m.SMALL_ID]["local_file_status"] = "MATCHED_REFERENCE_BYTES_NOT_PUBLISHER_SIGNATURE"
    forged["model_arms"][m.SMALL_ID]["local_observation"] = {
        "sha256": m.SMALL_THIRD_PARTY_SHA256, "size_bytes": 32_581_838}
    # Forged JSON cannot bypass actual local-file verification.
    with pytest.raises(ValueError, match="MODEL_FILE_NOT_ACCESSIBLE"):
        m.make_small_digest_candidate(d, forged, small_model_file=tmp_path / "missing")


def test_cannot_swap_model_roles_even_if_draft_digest_wrong(tmp_path):
    d = unpinned_draft()
    d["model_arms"][0]["checkpoint_sha256"] = m.MACE_MEDIUM_SHA256
    with pytest.raises(ValueError, match="SAME_WEIGHTS|REQUIRED|RHOMBUS"):
        m.inspect_supply(d)


def test_cli_generates_report_non_destructively(tmp_path, capsys):
    from scripts.benchmark.inspect_tier_a_supply_0204 import main
    d = unpinned_draft()
    src = tmp_path / "draft.json"; src.write_text(json.dumps(d), encoding="utf8")
    output = tmp_path / "out.json"
    result = main(["--draft", str(src), "--report", str(output)])
    assert result["execution_authorized"] is False
    assert json.loads(output.read_text())["model_arms"][m.SMALL_ID]["release_reported_sha256"] is None
    with pytest.raises(ValueError, match="ALREADY_EXISTS"):
        main(["--draft", str(src), "--report", str(output)])


def test_cli_refuses_output_overlap_and_duplicate_input(tmp_path):
    from scripts.benchmark.inspect_tier_a_supply_0204 import main
    d = unpinned_draft(); src = tmp_path / "draft.json"
    src.write_text(json.dumps(d), encoding="utf8")
    with pytest.raises(ValueError, match="OUTPUT_OVERLAPS"):
        main(["--draft", str(src), "--report", str(src)])
    duplicate = tmp_path / "dupe.json"
    duplicate.write_text('{"x":1,"x":2}', encoding="utf8")
    with pytest.raises(ValueError, match="DUPLICATE_JSON_KEY"):
        main(["--draft", str(duplicate), "--report", str(tmp_path / "out.json")])


def test_byte_hash_checker_rejects_mismatched_sha_after_expected_size(tmp_path):
    fake = tmp_path / "fake"
    fake.write_bytes(b"XXXX")
    with pytest.raises(ValueError, match="MODEL_SHA256_MISMATCH"):
        verify_local_binary_bytes(fake, expected_size_bytes=4, expected_sha256="0" * 64)


def test_cannot_generate_candidate_from_observation_without_bytes(tmp_path):
    d = unpinned_draft()
    fake_report = m.inspect_supply(d)
    fake_report["model_arms"][m.SMALL_ID]["local_file_status"] = "MATCHED_REFERENCE_BYTES_NOT_PUBLISHER_SIGNATURE"
    fake_report["model_arms"][m.SMALL_ID]["local_observation"] = {
        "sha256": m.SMALL_THIRD_PARTY_SHA256, "size_bytes": 32_581_838}
    fake_model = tmp_path / "synthetic-not-checkpoint"
    fake_model.write_bytes(b"fake")
    with pytest.raises(ValueError, match="MODEL_SIZE_MISMATCH"):
        m.make_small_digest_candidate(d, fake_report, small_model_file=fake_model)


def test_source_review_is_serializable_and_contains_no_paths(tmp_path):
    r = m.inspect_supply(unpinned_draft())
    encoded = json.dumps(r, sort_keys=True, allow_nan=False)
    assert "tmp_path" not in encoded
    assert "execution_authorized" in encoded
    assert "scientific_status" not in encoded or "NO_GO" in encoded


def test_synthetic_success_branch_proposes_only_an_unexecutable_candidate(monkeypatch, tmp_path):
    """Mocked verifier tests state flow; NEVER claims real checkpoint rehash."""
    d = unpinned_draft()
    pretend_file = tmp_path / "synthetic-stub-not-a-model.model"
    pretend_file.write_bytes(b"fake")
    called = []

    def synthetic_verifier(path, *, expected_sha256, expected_size_bytes):
        called.append((path, expected_sha256, expected_size_bytes))
        return {"sha256": expected_sha256, "size_bytes": expected_size_bytes}

    monkeypatch.setattr(m, "verify_local_binary_bytes", synthetic_verifier)
    review = m.inspect_supply(d, provided_files={m.SMALL_ID: pretend_file})
    candidate = m.make_small_digest_candidate(d, review, small_model_file=pretend_file)
    assert len(called) == 2  # candidate creation performs a second byte-verification call
    assert all(item[1:] == (m.SMALL_THIRD_PARTY_SHA256, 32_581_838) for item in called)
    assert d["model_arms"][0]["checkpoint_sha256"] is None
    assert candidate["model_arms"][0]["checkpoint_sha256"] == m.SMALL_THIRD_PARTY_SHA256
    assert candidate["execution_authorized"] is False
    assert candidate["benchmark_status"] == "BENCHMARK_NOT_FROZEN"
    assert "OWNER_RUN_AUTHORIZATION_MISSING" in m.inspect_budget_draft(candidate)["blockers"]


def test_model_fingerprint_candidate_rejects_wrong_report_context(tmp_path):
    d = unpinned_draft()
    r = m.inspect_supply(d)
    r["draft_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="SUPPLY_REPORT_CONTEXT_MISMATCH"):
        m.make_small_digest_candidate(d, r, small_model_file=tmp_path / "none")


def test_cli_candidate_request_fails_before_creating_any_output(tmp_path):
    from scripts.benchmark.inspect_tier_a_supply_0204 import main
    d = unpinned_draft()
    src = tmp_path / "draft.json"
    src.write_text(json.dumps(d), encoding="utf8")
    small = tmp_path / "wrong.model"
    small.write_bytes(b"NOT A MACE CHECKPOINT")
    report, candidate = tmp_path / "report.json", tmp_path / "candidate.json"
    with pytest.raises(ValueError, match="SMALL_MODEL_BYTES_MUST_BE_VERIFIED"):
        main(["--draft", str(src), "--small-model", str(small),
              "--report", str(report), "--candidate-draft", str(candidate)])
    assert not report.exists() and not candidate.exists()
