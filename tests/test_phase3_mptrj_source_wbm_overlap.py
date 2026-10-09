"""One-pass source-only MPTrj↔WBM overlap; small fixtures and no live GET."""
from __future__ import annotations

import io
import json
import hashlib

import pytest
from pymatgen.core import Lattice, Structure

from rhombus.domain.mptrj_integrity import verify_complete_mptrj_source
from rhombus.domain.overlap import WBMTargetRecord, build_wbm_target_index
from rhombus.domain.mptrj_source_overlap import MPTrjWBMSourceObserver, SourceOverlapError


def fixture(tmp_path):
    li=Structure(Lattice.cubic(4),["Li","O"],[[0,0,0],[.5,.5,.5]])
    na=Structure(Lattice.cubic(5),["Na","Cl"],[[0,0,0],[.5,.5,.5]])
    fp=lambda s:hashlib.sha256(s.composition.reduced_formula.encode()).hexdigest()
    group=lambda s:s.composition.reduced_formula
    db=tmp_path/"target.sqlite"
    build_wbm_target_index([
        WBMTargetRecord("wbm-1",li),WBMTargetRecord("wbm-2",na)
    ],db,source_file_sha256="a"*64,fingerprint=fp,prototype_group=group)
    raw=json.dumps({"mp-1":{
        "first":{"structure":li.as_dict()},
        "second":{"structure":li.as_dict()},
    }}).encode()
    return db,raw,dict(expected_wbm_sha256="a"*64,expected_wbm_count=2,
                       fingerprint=fp,prototype_group=group,
                       strict_match=lambda l,r:l==r,
                       near_match=lambda l,r:l.composition==r.composition)


def test_one_pass_exact_near_and_prototype_source_only(tmp_path):
    db,raw,kwargs=fixture(tmp_path)
    with MPTrjWBMSourceObserver(db,**kwargs) as observer:
        report=verify_complete_mptrj_source(
            io.BytesIO(raw),expected_size=len(raw),
            expected_md5=hashlib.md5(raw).hexdigest(),expected_frames=2,
            on_frame=observer.observe,
        )
        summary=observer.verified_source_summary(report)
    assert summary["mptrj_complete_frames"]==2
    assert summary["wbm_initial_structure_count"]==2
    assert summary["candidate_mptrj_frames"]==2
    assert summary["wbm_structures_strict_mptrj_source_match"]==1
    assert summary["wbm_structures_near_mptrj_source_match"]==1
    assert summary["wbm_structures_prototype_mptrj_source_overlap"]==1
    assert summary["mptrj_canonical_source_sha256"]==hashlib.sha256(raw).hexdigest()
    assert "SOURCE_ONLY" in summary["status"]
    assert summary["execute_training_exposure_audit"] is False
    assert summary["exact_mace_mpa0_training_membership_attested"] is False
    assert sorted(p.name for p in tmp_path.iterdir())==["target.sqlite"]


def test_fail_closed_on_whole_source_md5_drift_even_after_observing_frames(tmp_path):
    db,raw,kwargs=fixture(tmp_path)
    with MPTrjWBMSourceObserver(db,**kwargs) as observer:
        with pytest.raises(ValueError,match="MD5 mismatch"):
            verify_complete_mptrj_source(
                io.BytesIO(raw),expected_size=len(raw),
                expected_md5="0"*32,expected_frames=2,on_frame=observer.observe,
            )
        assert observer.frames==2
        with pytest.raises(SourceOverlapError,match="full original"):
            observer.verified_source_summary({})


def test_wrong_target_identity_refuses_before_source_read(tmp_path):
    db,raw,kwargs=fixture(tmp_path)
    kwargs["expected_wbm_sha256"]="f"*64
    with pytest.raises(SourceOverlapError,match="identity"):
        MPTrjWBMSourceObserver(db,**kwargs)


def test_wrong_target_row_count_or_missing_db_fails_closed(tmp_path):
    db,raw,kwargs=fixture(tmp_path)
    kwargs["expected_wbm_count"]=3
    with pytest.raises(SourceOverlapError,match="row count"):
        MPTrjWBMSourceObserver(db,**kwargs)
    with pytest.raises(SourceOverlapError,match="preexisting"):
        MPTrjWBMSourceObserver(tmp_path/"nonexistent.sqlite")


def test_unverified_model_training_claim_not_admitted(tmp_path):
    db,raw,kwargs=fixture(tmp_path)
    with MPTrjWBMSourceObserver(db,**kwargs) as observer:
        report=verify_complete_mptrj_source(
            io.BytesIO(raw),expected_size=len(raw),
            expected_md5=hashlib.md5(raw).hexdigest(),expected_frames=2,
            on_frame=observer.observe,
        )
        report["model_training_lineage"]["exact_mace_mpa0_training_frame_selection"]="ATTESTED"
        with pytest.raises(SourceOverlapError):
            observer.verified_source_summary(report)


def test_per_frame_observer_failure_aborts_full_verification_without_source_report(tmp_path):
    _,raw,_=fixture(tmp_path)
    observed=[]
    def reject_after_first(frame):
        observed.append(frame)
        raise RuntimeError("comparison failure")
    with pytest.raises(RuntimeError,match="comparison failure"):
        verify_complete_mptrj_source(
            io.BytesIO(raw),expected_size=len(raw),
            expected_md5=hashlib.md5(raw).hexdigest(),expected_frames=2,
            on_frame=reject_after_first,
        )
    assert len(observed)==1


def test_invalid_frame_callback_refused_before_reading():
    with pytest.raises(ValueError,match="on_frame must be callable"):
        verify_complete_mptrj_source(io.BytesIO(b""),expected_size=1,
                                     expected_md5="0"*32,expected_frames=1,on_frame=123)



def test_full_source_runner_wires_frames_to_observer_and_preserves_unknown(tmp_path, monkeypatch):
    from scripts.development import run_mptrj_wbm_source_overlap as runner
    from scripts.development import verify_mptrj_remote_stream as remote
    db, raw, opts = fixture(tmp_path)
    monkeypatch.setattr(remote, "canonical_source", lambda: {
        "file_id": 41619375, "file_name": "MPtrj_2022.9_full.json",
        "size": len(raw), "md5": hashlib.md5(raw).hexdigest(),
    })
    monkeypatch.setattr(remote, "OFFICIAL_MPTRJ_FRAMES", 2)
    obs = runner.run_source_only_overlap(
        db, open_url=lambda *args, **kwargs: _response(raw),
        observer_options=opts,
    )
    assert obs["mptrj_complete_frames"] == 2
    assert obs["wbm_structures_strict_mptrj_source_match"] == 1
    assert obs["exact_mace_mpa0_training_membership_attested"] is False


class _response:
    def __init__(self, raw):
        self.stream=io.BytesIO(raw)
        self.status=200
        self.headers={"Content-Length":str(len(raw))}
    def geturl(self):
        return "https://s3-eu-west-1.amazonaws.com/bucket/MPtrj.json"
    def read(self,n):
        assert 0 <= n <= 65536
        return self.stream.read(n)
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False


def test_runner_cli_refuses_missing_target_without_contacting_original(tmp_path, monkeypatch):
    from scripts.development import run_mptrj_wbm_source_overlap as runner
    monkeypatch.setattr(runner, "canonical_source", lambda: {"size": 999})
    network=[]
    monkeypatch.setattr(runner, "verify_remote_mptrj_full_stream",
                        lambda **kwargs: network.append(True))
    p=tmp_path/"missing.sqlite"
    report=tmp_path/"evidence.json"
    assert runner.main(["--preflight","--wbm-target-db",str(p)]) == 1
    assert runner.main(["--execute-full-download","--wbm-target-db",str(p),
                        "--report",str(report)]) == 1
    assert network==[]
    assert not report.exists()


def test_runner_cli_requires_new_report_before_full_source(tmp_path, monkeypatch):
    from scripts.development import run_mptrj_wbm_source_overlap as runner
    db, raw, opts = fixture(tmp_path)
    monkeypatch.setattr(runner, "canonical_source", lambda: {"size": len(raw)})
    observed=[]
    monkeypatch.setattr(runner, "run_source_only_overlap",
                        lambda *a,**kw: observed.append(True))
    report=tmp_path/"occupied.json"
    report.write_text("do not overwrite")
    assert runner.main(["--execute-full-download","--wbm-target-db",str(db),
                        "--report",str(report)]) == 1
    assert observed==[]
    assert report.read_text()=="do not overwrite"
