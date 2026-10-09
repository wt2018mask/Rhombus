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
