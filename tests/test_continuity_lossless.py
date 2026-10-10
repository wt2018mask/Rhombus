"""Regression: compact recovery must retain the supported science interface."""
import importlib.util
import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("continuity", ROOT / "scripts/development/continuity.py")
continuity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(continuity)
BASE_SHA = "e565e827119be40b23c21060bd59c873b895abaf"


def test_checkpoint_118_is_losslessly_accessible():
    baseline = json.loads(subprocess.check_output(["git", "show", f"{BASE_SHA}:data/development/CURRENT.json"], cwd=ROOT))
    result = subprocess.run(["python", "scripts/development/continuity.py", "resolve"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    effective = json.loads(result.stdout)
    assert len(baseline["refs"]) == 214
    assert len(baseline["state_codes"]) == 150
    assert baseline["refs"].items() <= effective["refs"].items()
    assert set(baseline["state_codes"]) <= set(effective["state_codes"])
    assert set(baseline["frontier"]["blockers"]) <= set(effective["frontier"]["blockers"])
    assert effective["frontier"]["parallel_workstream"] == baseline["frontier"]["parallel_workstream"]


BASE_DIGEST = "d9097ba231e5e01b598a7a4539dfa6a946c31396fcc2ef3bb37ebe085150618b"


@pytest.fixture
def sandbox(tmp_path):
    state = continuity.load_json(ROOT / "data/development/CURRENT.json")
    base_path = state["baseline"]["path"]
    snapshot = tmp_path / base_path
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes((ROOT / base_path).read_bytes())
    return state, snapshot, tmp_path


def test_snapshot_is_exact_canonical_bytes_and_history_is_supported():
    state = continuity.load_json(ROOT / "data/development/CURRENT.json")
    raw = (ROOT / state["baseline"]["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == BASE_DIGEST
    canonical = subprocess.check_output(["git", "show", f"{BASE_SHA}:data/development/CURRENT.json"], cwd=ROOT)
    assert raw == canonical
    result = subprocess.check_output(["python", "scripts/development/continuity.py", "resolve", "--baseline"], cwd=ROOT)
    assert json.loads(result) == json.loads(canonical)


def test_effective_handoff_and_checker_agree_and_keep_batch_a():
    raw = continuity.load_json(ROOT / "data/development/CURRENT.json")
    effective = continuity.resolve_state()
    assert len(effective["refs"]) == 221
    assert len(effective["state_codes"]) == 158
    assert raw["refs"].items() <= effective["refs"].items()
    assert set(raw["frontier"]["blockers"]) <= set(effective["frontier"]["blockers"])
    assert "PHASE3_SCIENTIFIC_NO_GO" in effective["state_codes"]
    assert "SALEX_NEW_SUBMISSIONS_DISABLED" in effective["state_codes"]
    assert "OPAQUE_EXPORTS_DENIED" in effective["state_codes"]
    assert "KAGGLE_ATOMIC_CONSUMPTION_UNAVAILABLE" in effective["frontier"]["blockers"]
    assert continuity.render_markdown(effective) == continuity.HANDOFF.read_text()
    assert not continuity.validate_repository()
    for key, path in effective["refs"].items():
        assert path.startswith("https://") or (ROOT / path).is_file(), key
        assert f"**{key}:** `{path}`" in continuity.HANDOFF.read_text()


def test_inherited_pointer_is_discoverable_without_git():
    result = subprocess.check_output(["python", "scripts/development/continuity.py", "resolve", "--ref", "salex_source_adapter"], cwd=ROOT, text=True)
    assert (ROOT / result.strip()).is_file()


@pytest.mark.parametrize("mutation", ["missing", "malformed", "modified", "wrong_hash", "wrong_version", "wrong_index", "wrong_path", "missing_field", "nested", "bad_schema", "bad_refs", "bad_codes", "bad_blockers", "duplicate_keys", "not_object"])
def test_invalid_snapshot_fails_closed(sandbox, mutation):
    state, snapshot, root = sandbox
    baseline = json.loads(snapshot.read_text())
    if mutation == "missing":
        snapshot.unlink()
    elif mutation == "modified":
        snapshot.write_bytes(snapshot.read_bytes() + b" ")
    elif mutation == "wrong_hash":
        state["baseline"]["sha256"] = "0" * 64
    elif mutation == "wrong_version":
        state["baseline"]["schema_version"] = "future"
    elif mutation == "wrong_index":
        state["baseline"]["checkpoint_index"] = 117
    elif mutation == "wrong_path":
        state["baseline"]["path"] = "../snapshot.json"
    elif mutation == "missing_field":
        del state["baseline"]["sha256"]
    else:
        if mutation == "malformed":
            payload = "{broken"
        elif mutation == "duplicate_keys":
            payload = '{"schema_version": "one", "schema_version": "two"}'
        elif mutation == "not_object":
            payload = "[]"
        else:
            if mutation == "nested":
                baseline["baseline"] = state["baseline"]
            elif mutation == "bad_schema":
                baseline["schema_version"] = "wrong"
            elif mutation == "bad_refs":
                baseline["refs"] = []
            elif mutation == "bad_codes":
                baseline["state_codes"] = "NO_GO"
            elif mutation == "bad_blockers":
                baseline["frontier"]["blockers"] = [None]
            payload = json.dumps(baseline)
        snapshot.write_text(payload)
        # Updated hash must not make invalid schema acceptable.
        state["baseline"]["sha256"] = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    with pytest.raises((ValueError, OSError)):
        continuity.resolve_state(state, root)
    # Every supported reader/writer must stop, without printing a partial delta.
    script = root / "scripts/development/continuity.py"
    script.parent.mkdir(parents=True)
    script.write_bytes((ROOT / "scripts/development/continuity.py").read_bytes())
    (root / "data/development/CURRENT.json").write_text(json.dumps(state))
    for command in ("resolve", "check", "write"):
        result = subprocess.run(["python", str(script), command], capture_output=True, text=True)
        assert result.returncode == 1, (mutation, command, result.stderr)
        assert "cannot resolve continuity" in result.stderr
        assert not result.stdout
    assert not (root / "docs/DEVELOPMENT_HANDOFF.md").exists()


def test_reference_rewrite_is_rejected():
    state = continuity.load_json(continuity.CURRENT)
    state["refs"]["architecture"] = "AGENTS.md"
    with pytest.raises(ValueError, match="cannot be rewritten"):
        continuity.resolve_state(state)


@pytest.mark.parametrize("path", ["data/missing-evidence.json", "../outside.json", "https-not-a-uri"])
def test_missing_or_unconfined_reference_is_rejected(path):
    state = continuity.load_json(continuity.CURRENT)
    state["refs"]["new_bad_pointer"] = path
    with pytest.raises(ValueError, match="unavailable repository reference"):
        continuity.resolve_state(state)


def test_explicit_external_reference_is_supported():
    state = continuity.load_json(continuity.CURRENT)
    state["refs"]["external_evidence"] = "https://example.org/evidence"
    assert continuity.resolve_state(state)["refs"]["external_evidence"] == "https://example.org/evidence"


def test_pr_checker_rejects_original_compaction_regression(monkeypatch):
    compact = continuity.load_json(continuity.CURRENT)
    del compact["baseline"]
    monkeypatch.setattr(continuity, "resolve_state", lambda *args: compact)
    monkeypatch.setattr(continuity, "validate_repository", lambda: [])
    errors = continuity.validate_pr(BASE_SHA, 283)
    assert "PR removed or rewrote previously accessible references" in errors
    assert "PR removed previously accessible state codes" in errors


def test_pr_checker_rejects_snapshot_rebinding_even_with_updated_hash(monkeypatch):
    raw = continuity.load_json(continuity.CURRENT)
    effective = continuity.resolve_state()
    raw["baseline"]["sha256"] = "1" * 64
    monkeypatch.setattr(continuity, "resolve_state", lambda *args: effective)
    monkeypatch.setattr(continuity, "validate_repository", lambda: [])
    original = continuity.load_json
    monkeypatch.setattr(continuity, "load_json", lambda path: copy.deepcopy(raw) if path == continuity.CURRENT else original(path))
    assert "new baseline must exactly preserve base CURRENT bytes" in continuity.validate_pr(BASE_SHA, 283)


def test_future_pr_cannot_modify_an_existing_snapshot(monkeypatch):
    raw = continuity.load_json(continuity.CURRENT)
    monkeypatch.setattr(continuity, "load_json_at_git_ref", lambda *args: raw)
    monkeypatch.setattr(continuity, "changed_paths", lambda *args: [("M", raw["baseline"]["path"])])
    assert f"immutable baseline changed: {raw['baseline']['path']}" in continuity.validate_pr(BASE_SHA, 283)
