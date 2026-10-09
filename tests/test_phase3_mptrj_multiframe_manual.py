"""Fixture-only tests: manual 1MiB observation, no network in CI."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest
import yaml
from pymatgen.core import Lattice, Structure

from scripts.development import observe_mptrj_multiframe_manual as mod
from scripts.development.probe_mptrj_source_prefix import inspect_first_complete_frame_prefix

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/phase3-mptrj-multiframe-1mib-manual.yml"


def prepare(monkeypatch):
    struct = Structure(Lattice.cubic(4), ["Li", "O"], [[0,0,0],[.5,.5,.5]])
    frame = {"structure":struct.as_dict(), "uncorrected_total_energy":-8.2,
             "corrected_total_energy":-8.0, "energy_per_atom":-4.0}
    data = json.dumps({"mp-1":{"first":frame,"second":frame}}).encode()
    raw = data + b" " * (1048576-len(data))
    previous = {"observation":{"prefix_sha256":sha256(raw[:262144]).hexdigest(),
                               "first_frame_structure":inspect_first_complete_frame_prefix(raw)},
                "source_metadata":{"expected_total_size_bytes_from_registry":12188168685}}
    monkeypatch.setattr(mod,"read_frozen_first_frame",lambda:deepcopy(previous))
    monkeypatch.setattr(mod,"canonical_source",lambda:{"size":12188168685,"file_id":41619375})
    calls=[]
    def probe(*,sample_capture=None,**kwargs):
        assert kwargs["prefix_bytes"]==1048576
        assert kwargs["require_complete_frame"] is True
        calls.append(kwargs)
        sample_capture(raw)
        return {"observation":{"prefix_sha256":sha256(raw).hexdigest()},
                "source_metadata":{"redirect_host":"cdn.example.org"}}
    monkeypatch.setattr(mod,"probe_https_range",probe)
    return raw,previous,calls


def test_manual_1mib_observation_two_complete_frames_and_closed_science(monkeypatch):
    raw,previous,calls=prepare(monkeypatch)
    report=mod.observe_real_bounded_multiframe()
    mod.validate_manual_multiframe_summary(report,prior=previous)
    assert len(calls)==1
    assert report["complete_frame_count"]==2
    assert report["prefix_1mib_sha256"]==sha256(raw).hexdigest()
    assert report["first_256k_sha256"]==previous["observation"]["prefix_sha256"]
    assert all(report[key] is False for key in mod.FALSE_FIELDS)
    assert report["complete_frames"][0]["material_id"]=="mp-1"


def test_cli_never_observes_without_explicit_flag_and_writes_metadata_only(tmp_path,monkeypatch,capsys):
    raw,previous,calls=prepare(monkeypatch)
    dest=tmp_path/"report.json"
    assert mod.main(["--verify",str(dest)])==1
    assert not calls
    assert mod.main(["--observe","--report",str(dest)])==0
    assert len(calls)==1
    assert 1 <= dest.stat().st_size <= 16384
    assert mod.main(["--observe","--report",str(dest)])==1
    assert len(calls)==1
    assert mod.main(["--verify",str(dest)])==0
    assert sorted(x.name for x in tmp_path.iterdir())==["report.json"]


@pytest.mark.parametrize("field,value",[
    ("full_source_verified",True),
    ("mace_mpa0_training_frames_attested",True),
    ("complete_frame_count",99),
    ("first_256k_sha256","0"*64),
])
def test_forbidden_science_claims_count_or_baseline_rejected(monkeypatch,field,value):
    _,prior,_=prepare(monkeypatch)
    report=mod.observe_real_bounded_multiframe()
    report[field]=value
    with pytest.raises(mod.ManualMultiFrameError):
        mod.validate_manual_multiframe_summary(report,prior=prior)


def test_changed_prefix_rejected_even_when_new_range_receipt_is_internally_consistent(monkeypatch):
    _,prior,calls=prepare(monkeypatch)
    prior["observation"]["prefix_sha256"]="0"*64
    monkeypatch.setattr(mod,"read_frozen_first_frame",lambda:prior)
    with pytest.raises(ValueError,match="frozen real observed source"):
        mod.observe_real_bounded_multiframe()
    assert len(calls)==1


def test_no_remote_get_if_frozen_archive_not_verifiable(monkeypatch):
    calls=[]
    monkeypatch.setattr(mod,"read_frozen_first_frame",
                        lambda: (_ for _ in ()).throw(mod.ManualMultiFrameError("invalid archive")))
    monkeypatch.setattr(mod,"probe_https_range",lambda **opts:calls.append(opts))
    with pytest.raises(mod.ManualMultiFrameError,match="invalid archive"):
        mod.observe_real_bounded_multiframe()
    assert calls==[]


def test_new_actions_workflow_manual_only_metadata_never_raw():
    cfg=yaml.load(WORKFLOW.read_text(),Loader=yaml.BaseLoader)
    assert set(cfg["on"])=={"workflow_dispatch"}
    assert cfg["permissions"]=={"contents":"read"}
    assert len(cfg["jobs"])==1
    steps=cfg["jobs"]["bounded-multiframe"]["steps"]
    run="\n".join(s.get("run","") for s in steps)
    assert "--observe --report" in run and "--verify" in run
    assert "--sample-output" not in run and "curl " not in run and "wget " not in run
    upload=[s for s in steps if s.get("uses","").startswith("actions/upload-artifact@")]
    assert len(upload)==1
    assert upload[0]["with"]["path"].endswith(".json")
    assert int(upload[0]["with"]["retention-days"])<=7
    assert steps[0]["with"]["persist-credentials"]=="false"
