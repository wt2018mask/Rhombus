"""Tests for the P2 validation harness (no GPU/MACE; stub runners only)."""

import json

import pytest

from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS
from rudeus.mlip.validation import (
    GPU_UNRESOLVED,
    VALIDATION_CASES,
    build_validation_report,
    check_cpu8000_eligible,
    collect_backend_versions,
    describe_comparison,
    detect_environment,
    resolve_case,
    run_validation,
    CaseUnavailable,
)


def _stub_result(job, state="PASS", lind=0.17):
    return {
        "candidate_material_id": job.get("child_material_id"),
        "batch_id": job["batch_id"],
        "p2_input_relaxed_sha256": job["relaxed_structure_sha256"],
        "p2_config_hash": job["p2_config_hash"],
        "seed": job["seed"],
        "dynamic_state": state,
        "host_framework_metrics": {
            "host_rmsd_final_A": 0.40, "host_rmsd_max_A": 0.50,
            "lindemann_provisional": lind, "min_distance_traj_A": 2.0,
            "volume_drift_fraction": 0.0, "coord_mean_change": 0.1},
        "thermal_metrics": {"temp_mean_K": 550.0, "temp_std_K": 80.0,
                            "energy_mean_ev_per_atom": -4.0,
                            "energy_drift_ev_per_ps_per_atom": 0.001},
        "mobile_ion_metrics": {"mobile_max_displacement_A": 1.0},
        "sampling_metrics": {"n_production_frames": 60},
        "termination": {"completed": True, "note": None},
        "reasons": ["stub"],
        "provenance": {},
        "evidence_events": [],
    }


def test_environment_never_claims_gpu_on_cpu():
    env = detect_environment()
    assert env["device"] == "cpu"
    assert env["cuda_available"] is False
    assert env["gpu_name"] is None
    assert env["gpu_validation_status"] == GPU_UNRESOLVED
    assert "cpu" not in str(env["gpu_name"])  # None, not a weasel string


def test_backend_versions_explicit():
    versions = collect_backend_versions()
    for key in ("python_version", "torch_version", "mace_version",
                "ase_version"):
        assert key in versions  # present even when a backend is missing


def test_missing_case_is_omission_not_substitution(tmp_path):
    with pytest.raises(CaseUnavailable, match="628136c9|no P1 done record"):
        resolve_case("628136c9", tmp_path / "empty")
    with pytest.raises(CaseUnavailable, match="unknown validation case"):
        resolve_case("not-a-case", tmp_path)
    with pytest.raises(CaseUnavailable, match="explicit relaxed-structure"):
        resolve_case("control-1e9", tmp_path)


def test_cpu8000_guard_is_control_only():
    check_cpu8000_eligible(["control-1e9"])
    with pytest.raises(ValueError, match="exactly the control"):
        check_cpu8000_eligible(["control-1e9", "0d4de6bc"])
    with pytest.raises(ValueError, match="exactly the control"):
        check_cpu8000_eligible(["0d4de6bc"])


def test_validation_run_preserves_identity_and_verdict(tmp_path):
    if not __import__("pathlib").Path("data/obelix").exists():
        pytest.skip("needs repo data layout for resolve paths")
    import shutil
    from pathlib import Path
    src = Path("data/batches/done/0d4de6bc17174a64.json")
    if not src.exists():
        pytest.skip("marginal P1 record absent")
    p1done, records = tmp_path / "p1done", tmp_path / "records"
    p1done.mkdir()
    shutil.copy(src, p1done / src.name)
    proto = dict(P2_PROTOCOL_DEFAULTS)
    out = run_validation(["0d4de6bc", "628136c9"],
                         lambda job: _stub_result(job, state="INDETERMINATE"),
                         records, p1done, proto, {"0d4de6bc": 11},
                         {"session": "t"})
    assert out["0d4de6bc"]["status"] == "processed"
    assert out["0d4de6bc"]["regime"] == "marginal"
    assert out["628136c9"]["status"] == "omitted"  # recorded, not replaced
    payload = json.loads(
        (records / "p2val-0d4de6bc.run0.json").read_text(encoding="utf-8"))
    assert payload["validation"]["case_id"] == "0d4de6bc"
    assert payload["result"]["dynamic_state"] == "INDETERMINATE"  # untouched
    assert payload["result"]["seed"] == 11
    assert "diffus" not in json.dumps(payload).lower()


def test_comparison_describes_without_verdicts():
    cpu = _stub_result({"child_material_id": "c", "batch_id": "b",
                        "relaxed_structure_sha256": "s",
                        "p2_config_hash": "h", "seed": 1},
                       state="PASS", lind=0.17)
    gpu = _stub_result({"child_material_id": "c", "batch_id": "b",
                        "relaxed_structure_sha256": "s",
                        "p2_config_hash": "h", "seed": 1},
                       state="INDETERMINATE", lind=0.21)
    desc = describe_comparison(cpu, gpu)
    lind = desc["metric_deltas"][
        "host_framework_metrics.lindemann_provisional"]
    assert lind["delta"] == pytest.approx(0.04)
    assert lind["cpu_gate_side"] == "below"
    assert lind["gpu_gate_side"] == "above"
    assert desc["states_agree"] is False
    assert "verdict" not in desc and "score" not in json.dumps(desc)
    same = describe_comparison(cpu, dict(cpu))
    assert same["metric_deltas"][
        "host_framework_metrics.lindemann_provisional"]["delta"] == 0.0
    assert same["states_agree"] is True


def test_report_deterministic_and_marks_unresolved(tmp_path):
    env = {"device": "cpu", "cuda_available": False, "gpu_name": None,
           "gpu_validation_status": GPU_UNRESOLVED}
    kwargs = dict(cases=["0d4de6bc"], records_dir=tmp_path,
                  protocol=dict(P2_PROTOCOL_DEFAULTS),
                  calc_info={"name": "m", "url": "u", "sha256": "s"},
                  environment=env, git_commit="abc123",
                  timestamp="2026-09-13T00:00:00+00:00")
    a = build_validation_report(**kwargs)
    b = build_validation_report(**kwargs)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert a["gpu_validation_status"] == GPU_UNRESOLVED
    assert a["summary"]["n_missing_cases"] == 1  # no records yet
    assert "unresolved" in a["scientific_status"].lower()
    assert a["cases_requested"] == ["0d4de6bc"]
    assert set(VALIDATION_CASES) >= {"control-1e9", "0d4de6bc", "f8857e1e",
                                     "4a9735f2", "628136c9",
                                     "synthetic-overlap"}


def test_report_extra_records_cancelled_attempt(tmp_path):
    """A cancelled (never-executed) attempt is recorded explicitly, not as data."""
    env = {"device": "cpu", "cuda_available": False, "gpu_name": None,
           "gpu_validation_status": GPU_UNRESOLVED}
    kwargs = dict(cases=["control-1e9"], records_dir=tmp_path,
                  protocol=dict(P2_PROTOCOL_DEFAULTS),
                  calc_info={"name": "m", "url": "u", "sha256": "s"},
                  environment=env, git_commit="abc123",
                  timestamp="2026-09-13T00:00:00+00:00",
                  extra={"cancelled_attempts": [{
                      "what": "cpu-8000 control run",
                      "status": "CANCELLED",
                      "reason": "operator stop; CPU trajectory cannot resolve "
                                "the GPU validation question"}]})
    report = build_validation_report(**kwargs)
    assert report["cancelled_attempts"][0]["status"] == "CANCELLED"
    assert report["summary"]["n_runs"] == 0  # absence is not a result
    assert report["gpu_validation_status"] == GPU_UNRESOLVED


def test_run_index_base_coexists_across_seeds(tmp_path):
    """Two invocations with different seeds keep both records (no overwrite)."""
    import shutil
    from pathlib import Path
    src = Path("data/batches/done/0d4de6bc17174a64.json")
    if not src.exists():
        pytest.skip("marginal P1 record absent")
    p1done, records = tmp_path / "p1done", tmp_path / "records"
    p1done.mkdir()
    shutil.copy(src, p1done / src.name)
    proto = dict(P2_PROTOCOL_DEFAULTS)
    run_validation(["0d4de6bc"], lambda job: _stub_result(job), records,
                   p1done, proto, {"0d4de6bc": 11}, {"session": "t"},
                   run_index_base=0)
    run_validation(["0d4de6bc"], lambda job: _stub_result(job), records,
                   p1done, proto, {"0d4de6bc": 22}, {"session": "t"},
                   run_index_base=1)
    files = sorted(p.name for p in records.glob("*.json"))
    assert files == ["p2val-0d4de6bc.run0.json", "p2val-0d4de6bc.run1.json"]
    seeds_seen = sorted(
        json.loads((records / f).read_text(encoding="utf-8"))["job"]["seed"]
        for f in files)
    assert seeds_seen == [11, 22]


def test_control_fixture_resolves():
    """Committed control fixture loads 28-site relaxed structure with provenance."""
    from pathlib import Path
    fix = Path("data/batches/audit/p2_validation_control_1e9.json")
    if not fix.exists():
        pytest.skip("control fixture absent")
    info = resolve_case("control-1e9", "data/batches/done",
                        control_input=fix)
    assert len(info["structure_dict"]["sites"]) == 28
    assert info["child_material_id"] == "CONTROL-1e9"
    assert info["p1_checkpoint"]["sha256"] == \
        "75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638"


def test_kaggle_notebook_wrapper_valid():
    """Notebook: valid nbformat, pinned commit, real CLI flags, no secrets."""
    import re
    from pathlib import Path
    import nbformat

    path = Path("notebooks/kaggle_p2_gpu_validation.ipynb")
    if not path.exists():
        pytest.skip("kaggle notebook absent")
    nb = nbformat.read(str(path), as_version=4)
    nbformat.validate(nb)
    sources = "\n".join(
        "".join(c.get("source", [])) if isinstance(c.get("source"), list)
        else c.get("source", "") for c in nb.cells)
    assert "44029b861044cdc615dcabbdb5f1a77e20b5bc8d" in sources  # pinned SHA
    assert "python -m rudeus.mlip.validation" in sources
    assert "--run-index-base" in sources and "--seed-base" in sources
    lowered = sources.lower()
    for pattern in ("ghp_", "github_pat_", "gho_", "x-access-token",
                    "passwd", "password="):
        assert pattern not in lowered, f"possible secret: {pattern}"
    assert re.search(r'\bpat\s*=\s*["\']', sources) is None
    assert re.search(r'\btoken\s*=\s*["\']', sources) is None
    assert "github.com/wt2018mask/Rhombus" in sources
    flags = set(re.findall(r"--[\w-]+", sources))
    known = {"--cases", "--control-input", "--records-dir", "--report",
             "--device", "--worker", "--seed-base", "--run-index-base",
             "--run", "--cpu-8000", "--p1-done", "--out", "--equil-steps",
             "--prod-steps", "--sample-interval", "--config",
             "--porcelain",  # git status flag, not a harness flag
             "--is-ancestor", "--name-only", "--cached", "--short",
             "--rev-parse", "--format"}  # read-only git plumbing
    assert flags <= known, f"unknown CLI flags referenced: {flags - known}"


def test_kaggle_notebook_persistence_safety():
    """Persistence cells: secrets via Kaggle Secrets only, no force, no main,
    branch from SHARD, explicit result-only staging, no scientific writes."""
    import re
    from pathlib import Path
    import nbformat

    path = Path("notebooks/kaggle_p2_gpu_validation.ipynb")
    if not path.exists():
        pytest.skip("kaggle notebook absent")
    nb = nbformat.read(str(path), as_version=4)
    code = "\n".join(
        "".join(c.get("source", [])) if isinstance(c.get("source"), list)
        else c.get("source", "")
        for c in nb.cells if c.cell_type == "code")
    # secrets: named secret only, never literals or embedded credentials
    assert 'get_secret("GITHUB_PAT")' in code
    assert re.search(r'\bPAT\s*=\s*["\']', code) is None
    # no literal credentials in URLs: every authenticated URL must use the
    # in-memory {PAT} template (sanctioned), never a literal secret
    for m in re.finditer(r'https://\S*@github\.com', code):
        assert "{PAT}" in m.group(0), f"literal credential URL: {m.group(0)[:40]}"
    # no destructive git: force-push / hard reset / clean / rebase as commands
    assert re.search(r'push\s+(-f|--force)\b', code) is None
    assert "reset --hard" not in code
    assert "clean -fd" not in code
    assert "git rebase" not in code
    # never main: no main-branch push targets
    assert "refs/heads/main" not in code
    assert "push origin main" not in code
    assert "HEAD:main" not in code
    # branch derived deterministically from SHARD
    assert "p2-gpu-validation-s{SHARD}" in code
    assert re.search(r"^SHARD = [01]\b", code, re.MULTILINE) is not None
    # staging is explicit result-only pathspec
    assert '["git", "add", "--"]' in code
    assert "git add -A" not in code
    assert "p2_gpu_validation/s" in code
    # persistence never writes scientific source files: no write-mode open()
    # anywhere in notebook code cells (reads use bare encoding= kwarg)
    assert re.search(r"open\([^)]*['\"]w", code) is None
    assert re.search(r"open\([^)]*['\"]a", code) is None
