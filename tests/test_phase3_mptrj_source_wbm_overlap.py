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
                       near_match=lambda l,r:l.composition==r.composition,
                       allow_custom_protocols_for_fixture=True)


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
    # SQLite WAL mode may legitimately retain -wal and -shm sidecars.
    # No original MPTrj bytes or a partially attested report may be written.
    paths = {p.name for p in tmp_path.iterdir()}
    assert "target.sqlite" in paths
    assert paths <= {"target.sqlite", "target.sqlite-wal", "target.sqlite-shm"}


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



def test_each_matched_wbm_target_has_distinct_source_only_flags_and_no_unseen_claim(tmp_path):
    db,raw,kwargs=fixture(tmp_path)
    with MPTrjWBMSourceObserver(db,**kwargs) as observer:
        verified=verify_complete_mptrj_source(
            io.BytesIO(raw),expected_size=len(raw),
            expected_md5=hashlib.md5(raw).hexdigest(),expected_frames=2,
            on_frame=observer.observe,
        )
        matches=list(observer.iter_verified_matched_targets(verified))
    assert len(matches)==1
    assert matches[0]["material_id"]=="wbm-1"
    assert matches[0]["strict_original_source_structure_match"] is True
    assert matches[0]["near_original_source_structure_match"] is True
    assert matches[0]["original_source_prototype_overlap"] is True
    assert matches[0]["strict_source_frame_locator"] == "/mp-1/first"
    assert matches[0]["near_source_frame_locator"] == "/mp-1/first"
    assert matches[0]["prototype_source_frame_locator"] == "/mp-1/first"
    assert matches[0]["model_training_membership_attested"] is False
    assert matches[0]["unseen_generalization_claim"] is False
    assert "structure" not in matches[0]


def test_source_only_target_rows_cannot_be_emitted_without_original_integrity(tmp_path):
    db,raw,kwargs=fixture(tmp_path)
    with MPTrjWBMSourceObserver(db,**kwargs) as observer:
        verified=verify_complete_mptrj_source(
            io.BytesIO(raw),expected_size=len(raw),
            expected_md5=hashlib.md5(raw).hexdigest(),expected_frames=2,
            on_frame=observer.observe,
        )
        broken = dict(verified)
        broken["source_identity"]={**verified["source_identity"], "figshare_md5_matched":False}
        with pytest.raises(SourceOverlapError,match="full original"):
            list(observer.iter_verified_matched_targets(broken))


def test_verified_target_rows_callback_runs_after_complete_source_no_unverified(tmp_path,monkeypatch):
    from scripts.development import verify_mptrj_remote_stream as remote
    from scripts.development import run_mptrj_wbm_source_overlap as runner
    db,raw,opts=fixture(tmp_path)
    monkeypatch.setattr(remote,"canonical_source",lambda:{
        "file_id":41619375,"file_name":"MPtrj_2022.9_full.json",
        "size":len(raw),"md5":hashlib.md5(raw).hexdigest(),
    })
    monkeypatch.setattr(remote,"OFFICIAL_MPTRJ_FRAMES",2)
    collected=[]
    result=runner.run_source_only_overlap(
        db,open_url=lambda *a,**kw:_response(raw),observer_options=opts,
        on_verified_targets=lambda rows: collected.extend(rows) or len(collected),
    )
    assert len(collected)==1
    assert result["source_only_matched_wbm_rows_exported"]==1
    assert result["mptrj_complete_frames"]==2


def test_staged_source_only_jsonl_never_publishes_partial_or_overwrites(tmp_path):
    from scripts.development.run_mptrj_wbm_source_overlap import _StagedTargetRows
    path=tmp_path/"matches.jsonl"
    stage=_StagedTargetRows(path)
    with pytest.raises(ValueError,match="model membership"):
        stage(iter([
            {"model_training_membership_attested":False,"material_id":"wbm-1"},
            {"model_training_membership_attested":True,"material_id":"wbm-2"},
        ]))
    assert not path.exists()
    stage.discard()
    assert not list(tmp_path.iterdir())
    stage=_StagedTargetRows(path)
    assert stage(iter([{"model_training_membership_attested":False,
                       "material_id":"wbm-1"}]))==1
    stage.publish()
    assert path.read_text().count("\n")==1
    assert "wbm-1" in path.read_text()
    stage2=_StagedTargetRows(path)
    with pytest.raises(ValueError,match="new file"):
        stage2(iter([{"model_training_membership_attested":False}]))
    assert "wbm-1" in path.read_text()


def test_source_target_positive_only_match_export_after_digest_failure(tmp_path,monkeypatch):
    from scripts.development import verify_mptrj_remote_stream as remote
    from scripts.development import run_mptrj_wbm_source_overlap as runner
    db,raw,opts=fixture(tmp_path)
    monkeypatch.setattr(remote,"canonical_source",lambda:{
        "file_id":41619375,"file_name":"MPtrj_2022.9_full.json",
        "size":len(raw),"md5":"f"*32,
    })
    monkeypatch.setattr(remote,"OFFICIAL_MPTRJ_FRAMES",2)
    stage=runner._StagedTargetRows(tmp_path/"matches.jsonl")
    with pytest.raises(ValueError,match="MD5 mismatch"):
        runner.run_source_only_overlap(
            db,open_url=lambda *a,**kw:_response(raw),observer_options=opts,
            on_verified_targets=stage,
        )
    stage.discard()
    assert not (tmp_path/"matches.jsonl").exists()
    assert not any(p.name.endswith("jsonl.tmp") for p in tmp_path.iterdir())



def test_source_witness_prefers_first_full_frame_and_never_uses_last(tmp_path):
    db, raw, opts = fixture(tmp_path)
    with MPTrjWBMSourceObserver(db, **opts) as obs:
        proof = verify_complete_mptrj_source(
            io.BytesIO(raw), expected_size=len(raw),
            expected_md5=hashlib.md5(raw).hexdigest(), expected_frames=2,
            on_frame=obs.observe,
        )
        rows = list(obs.iter_verified_matched_targets(proof))
    assert len(rows) == 1
    assert all(rows[0][key] == "/mp-1/first" for key in (
        "strict_source_frame_locator", "near_source_frame_locator",
        "prototype_source_frame_locator",
    ))
    assert rows[0]["model_training_membership_attested"] is False


def test_prototype_only_target_has_no_strict_or_near_witness(tmp_path):
    from rhombus.domain.overlap import WBMTargetRecord, build_wbm_target_index
    from pymatgen.core import Structure, Lattice
    a = Structure(Lattice.cubic(4), ["Li", "O"], [[0,0,0], [.5,.5,.5]])
    b = Structure(Lattice.cubic(5), ["Na", "Cl"], [[0,0,0], [.5,.5,.5]])
    db = tmp_path / "prototype-targets.sqlite"
    fp = lambda s: hashlib.sha256(s.composition.reduced_formula.encode()).hexdigest()
    proto = lambda s: "same-group"
    build_wbm_target_index(
        [WBMTargetRecord("wbm-a", a), WBMTargetRecord("wbm-b", b)],
        db, source_file_sha256="c"*64, fingerprint=fp, prototype_group=proto,
    )
    raw = json.dumps({"mp-frame": {"first": {"structure": a.as_dict()}}}).encode()
    with MPTrjWBMSourceObserver(
        db, expected_wbm_sha256="c"*64, expected_wbm_count=2,
        fingerprint=fp, prototype_group=proto,
        strict_match=lambda x,y: x == y,
        near_match=lambda x,y: x.composition == y.composition,
        allow_custom_protocols_for_fixture=True,
    ) as obs:
        full = verify_complete_mptrj_source(
            io.BytesIO(raw), expected_size=len(raw),
            expected_md5=hashlib.md5(raw).hexdigest(), expected_frames=1,
            on_frame=obs.observe,
        )
        rows = list(obs.iter_verified_matched_targets(full))
    assert [r["material_id"] for r in rows] == ["wbm-a", "wbm-b"]
    assert rows[1]["strict_original_source_structure_match"] is False
    assert rows[1]["near_original_source_structure_match"] is False
    assert rows[1]["original_source_prototype_overlap"] is True
    assert rows[1]["strict_source_frame_locator"] is None
    assert rows[1]["near_source_frame_locator"] is None
    assert rows[1]["prototype_source_frame_locator"] == "/mp-frame/first"
    assert rows[1]["unseen_generalization_claim"] is False


def test_frame_witness_cannot_be_exported_from_unverified_hash(tmp_path):
    db, raw, opts = fixture(tmp_path)
    with MPTrjWBMSourceObserver(db, **opts) as obs:
        verified = verify_complete_mptrj_source(
            io.BytesIO(raw), expected_size=len(raw),
            expected_md5=hashlib.md5(raw).hexdigest(), expected_frames=2,
            on_frame=obs.observe,
        )
        verified["frame_coverage"]["complete_json_consumed"] = False
        with pytest.raises(SourceOverlapError):
            list(obs.iter_verified_matched_targets(verified))



def test_custom_protocol_target_index_cannot_enter_production_source_observer(tmp_path):
    db, _, opts = fixture(tmp_path)
    opts.pop("allow_custom_protocols_for_fixture")
    with pytest.raises(SourceOverlapError, match="fixture-only"):
        MPTrjWBMSourceObserver(db, **opts)


def test_index_protocol_tampering_refused_before_any_original_source_read(tmp_path, monkeypatch):
    import sqlite3
    from scripts.development import run_mptrj_wbm_source_overlap as runner
    db, _, opts = fixture(tmp_path)
    with sqlite3.connect(db) as connection:
        connection.execute(
            "UPDATE metadata SET value = ? WHERE key = ?",
            ("different-fingerprint-protocol", "candidate_fingerprint_protocol_id"),
        )
        connection.commit()
    called = []
    monkeypatch.setattr(
        runner, "verify_remote_mptrj_full_stream",
        lambda **kw: called.append(True),
    )
    with pytest.raises(SourceOverlapError, match="protocols"):
        runner.run_source_only_overlap(db, observer_options=opts)
    assert called == []


def test_mismatched_prototype_protocol_refused_before_network(tmp_path):
    import sqlite3
    db, _, opts = fixture(tmp_path)
    with sqlite3.connect(db) as connection:
        connection.execute(
            "UPDATE metadata SET value = ? WHERE key = ?",
            ("different-prototype-protocol", "prototype_group_protocol_id"),
        )
        connection.commit()
    with pytest.raises(SourceOverlapError, match="protocols"):
        MPTrjWBMSourceObserver(db, **opts)


def test_old_index_without_protocol_metadata_must_not_be_reused(tmp_path):
    import sqlite3
    db, _, opts = fixture(tmp_path)
    with sqlite3.connect(db) as connection:
        connection.execute(
            "DELETE FROM metadata WHERE key = ?", ("prototype_group_protocol_id",)
        )
        connection.commit()
    with pytest.raises(SourceOverlapError, match="protocols"):
        MPTrjWBMSourceObserver(db, **opts)



def test_frozen_candidate_index_detects_tampered_bucket_before_network(tmp_path, monkeypatch):
    import sqlite3
    from rhombus.domain.structure_protocols import structure_candidate_fingerprint_sha256
    from scripts.development import run_mptrj_wbm_source_overlap as runner
    from scripts.development import verify_mptrj_remote_stream as remote

    db, raw, opts = fixture(tmp_path)
    # Fixture custom prototype is explicit, but candidate fingerprint must
    # use the exact frozen function so the self-check is active.
    from pymatgen.core import Structure, Lattice
    struct=Structure(Lattice.cubic(4),["Li","O"],[[0,0,0],[.5,.5,.5]])
    from rhombus.domain.overlap import WBMTargetRecord, build_wbm_target_index
    checked=tmp_path/"strict-fingerprint.sqlite"
    build_wbm_target_index(
        [WBMTargetRecord("wbm-frozen",struct)],
        checked, source_file_sha256="c"*64,
        prototype_group=opts["prototype_group"],
    )
    with sqlite3.connect(checked) as connection:
        connection.execute(
            "UPDATE targets SET candidate_fingerprint_sha256 = ? WHERE material_id = ?",
            ("0"*64,"wbm-frozen"),
        )
        connection.commit()
    observed=[]
    monkeypatch.setattr(runner,"verify_remote_mptrj_full_stream",
                        lambda **kwargs:observed.append(True))
    with pytest.raises(SourceOverlapError,match="candidate fingerprint"):
        runner.run_source_only_overlap(checked, observer_options={
            "expected_wbm_sha256":"c"*64,
            "expected_wbm_count":1,
            "prototype_group":opts["prototype_group"],
            "allow_custom_protocols_for_fixture":True,
        })
    assert observed == []


def test_frozen_candidate_index_accepts_matching_rows_and_nonempty_scope(tmp_path):
    from rhombus.domain.overlap import WBMTargetRecord, build_wbm_target_index
    from pymatgen.core import Lattice, Structure
    a=Structure(Lattice.cubic(5),["Na","Cl"],[[0,0,0],[.5,.5,.5]])
    db=tmp_path/"valid-index.sqlite"
    build_wbm_target_index(
        [WBMTargetRecord("wbm-valid",a)],db,
        source_file_sha256="d"*64,
        prototype_group=_fixture_proto,
    )
    with MPTrjWBMSourceObserver(
        db, expected_wbm_sha256="d"*64, expected_wbm_count=1,
        prototype_group=_fixture_proto,
        allow_custom_protocols_for_fixture=True,
    ) as obs:
        assert obs.wbm_count == 1


def _fixture_proto(structure):
    return "fixture-proto"



def _verified_bound_source_export_pair(tmp_path, monkeypatch):
    from scripts.development import verify_mptrj_remote_stream as remote
    from scripts.development import run_mptrj_wbm_source_overlap as runner
    db, raw, opts = fixture(tmp_path)
    monkeypatch.setattr(remote, "canonical_source", lambda: {
        "file_id":41619375, "file_name":"MPtrj_2022.9_full.json",
        "size":len(raw), "md5":hashlib.md5(raw).hexdigest(),
    })
    monkeypatch.setattr(remote, "OFFICIAL_MPTRJ_FRAMES", 2)
    matches=tmp_path/"source-positive.jsonl"
    stage=runner._StagedTargetRows(matches)
    report=runner.run_source_only_overlap(
        db, open_url=lambda *a, **kw: _response(raw),
        observer_options=opts, on_verified_targets=stage,
    )
    stage.publish()
    summary=tmp_path/"source-report.json"
    summary.write_text(json.dumps(report))
    return summary, matches, report


def test_verified_source_only_export_pair_recomputes_exact_bytes_and_witnesses(tmp_path,monkeypatch):
    from scripts.development.verify_mptrj_wbm_source_target_export import verify_pair
    summary, matches, report = _verified_bound_source_export_pair(tmp_path,monkeypatch)
    assert report["source_only_matched_wbm_rows_exported"] == 1
    assert report["source_only_matched_wbm_jsonl_sha256"] == hashlib.sha256(
        matches.read_bytes()
    ).hexdigest()
    proof=verify_pair(summary, matches, expected_wbm_sha256="a"*64, expected_wbm_count=2)
    assert proof["matched_rows"] == 1
    assert proof["model_training_membership_attested"] is False
    assert proof["unseen_generalization_claim"] is False


def test_verified_source_only_export_refuses_jsonl_tampering(tmp_path,monkeypatch):
    from scripts.development.verify_mptrj_wbm_source_target_export import (
        verify_pair, SourceTargetPairError,
    )
    summary, matches, _ = _verified_bound_source_export_pair(tmp_path,monkeypatch)
    matches.write_bytes(matches.read_bytes().replace(b"wbm-1",b"wbm-x"))
    with pytest.raises(SourceTargetPairError,match="SHA256"):
        verify_pair(summary, matches, expected_wbm_sha256="a"*64, expected_wbm_count=2)


def test_verified_source_only_export_refuses_unbound_or_promoted_report(tmp_path,monkeypatch):
    from scripts.development.verify_mptrj_wbm_source_target_export import (
        verify_pair, SourceTargetPairError,
    )
    summary, matches, payload = _verified_bound_source_export_pair(tmp_path,monkeypatch)
    payload.pop("source_only_matched_wbm_jsonl_sha256")
    summary.write_text(json.dumps(payload))
    with pytest.raises(SourceTargetPairError,match="digest"):
        verify_pair(summary, matches, expected_wbm_sha256="a"*64, expected_wbm_count=2)
    payload["source_only_matched_wbm_jsonl_sha256"] = hashlib.sha256(matches.read_bytes()).hexdigest()
    payload["unseen_generalization_claim"] = True
    summary.write_text(json.dumps(payload))
    with pytest.raises(SourceTargetPairError,match="scope"):
        verify_pair(summary, matches, expected_wbm_sha256="a"*64, expected_wbm_count=2)


def test_verified_source_only_export_rejects_positive_without_witness_even_when_hash_matches(tmp_path,monkeypatch):
    from scripts.development.verify_mptrj_wbm_source_target_export import (
        verify_pair, SourceTargetPairError,
    )
    summary, matches, report = _verified_bound_source_export_pair(tmp_path,monkeypatch)
    rows = matches.read_text().splitlines()
    row=json.loads(rows[0])
    row["near_source_frame_locator"]=None
    changed=(json.dumps(row, sort_keys=True, separators=(",",":"))+"\n").encode()
    matches.write_bytes(changed)
    report["source_only_matched_wbm_jsonl_sha256"]=hashlib.sha256(changed).hexdigest()
    summary.write_text(json.dumps(report))
    with pytest.raises(SourceTargetPairError,match="frame witness"):
        verify_pair(summary, matches, expected_wbm_sha256="a"*64, expected_wbm_count=2)


def test_verified_source_only_export_refuses_missing_source_member_and_extra_row(tmp_path,monkeypatch):
    from scripts.development.verify_mptrj_wbm_source_target_export import (
        verify_pair, SourceTargetPairError,
    )
    summary, matches, report = _verified_bound_source_export_pair(tmp_path,monkeypatch)
    row=json.loads(matches.read_text())
    row["material_id"]="wbm-z"
    with matches.open("ab") as out:
        out.write((json.dumps(row,sort_keys=True,separators=(",",":"))+"\n").encode())
    report["source_only_matched_wbm_jsonl_sha256"]=hashlib.sha256(matches.read_bytes()).hexdigest()
    summary.write_text(json.dumps(report))
    with pytest.raises(SourceTargetPairError,match="more matched"):
        verify_pair(summary, matches, expected_wbm_sha256="a"*64, expected_wbm_count=2)


def test_verification_cli_is_offline_and_rejects_unbound_files(tmp_path,monkeypatch):
    from scripts.development.verify_mptrj_wbm_source_target_export import main
    assert main(["--aggregate-report",str(tmp_path/"missing.json"),
                 "--matched-targets-jsonl",str(tmp_path/"missing.jsonl")]) == 1



def test_old_site_count_candidate_bucket_rejected_as_incompatible_before_source_get(
    tmp_path, monkeypatch
):
    import sqlite3
    from scripts.development import run_mptrj_wbm_source_overlap as runner
    db, _, opts = fixture(tmp_path)
    with sqlite3.connect(db) as con:
        con.execute(
            "UPDATE metadata SET value = ? WHERE key = ?",
            ("rhombus-composition-site-count-candidate-fingerprint-v1",
             "candidate_fingerprint_protocol_id"),
        )
    called = []
    monkeypatch.setattr(
        runner, "verify_remote_mptrj_full_stream",
        lambda **kwargs: called.append(True),
    )
    with pytest.raises(SourceOverlapError, match="protocols"):
        runner.run_source_only_overlap(db, observer_options=opts)
    assert called == []


def test_wbm_v2_original_source_observer_compares_supercell_candidate(tmp_path):
    from rhombus.domain.structure_protocols import (
        structure_candidate_fingerprint_sha256,
    )
    base = Structure(Lattice.cubic(5), ["Na", "Cl"],
                     [[0, 0, 0], [.5, .5, .5]])
    enlarged = base.copy()
    enlarged.make_supercell([2, 1, 1])
    db = tmp_path / "supercell-target.sqlite"
    # Prototype callback is fixture-only and deliberately does not widen
    # the claim to model training membership.
    build_wbm_target_index(
        [WBMTargetRecord("wbm-super", enlarged)], db,
        source_file_sha256="f"*64, prototype_group=_fixture_proto,
    )
    raw = json.dumps({"mp-1": {"first": {"structure": base.as_dict()}}}).encode()
    with MPTrjWBMSourceObserver(
        db, expected_wbm_sha256="f"*64, expected_wbm_count=1,
        prototype_group=_fixture_proto,
        allow_custom_protocols_for_fixture=True,
    ) as obs:
        verified = verify_complete_mptrj_source(
            io.BytesIO(raw), expected_size=len(raw),
            expected_md5=hashlib.md5(raw).hexdigest(), expected_frames=1,
            on_frame=obs.observe,
        )
        matches = list(obs.iter_verified_matched_targets(verified))
    assert obs.candidate_frames == 1
    assert len(matches) == 1
    assert matches[0]["near_original_source_structure_match"] is True
    assert matches[0]["strict_original_source_structure_match"] is False
    assert matches[0]["model_training_membership_attested"] is False



def test_v2_bucket_profile_tracks_sitecount_expansion_without_source_fetch(tmp_path):
    from rhombus.domain.structure_protocols import structure_candidate_fingerprint_sha256
    base = Structure(Lattice.cubic(5), ["Na", "Cl"], [[0,0,0],[.5,.5,.5]])
    supercell = base.copy()
    supercell.make_supercell([2,1,1])
    alt = Structure(Lattice.cubic(4),["Li","O"],[[0,0,0],[.5,.5,.5]])
    db = tmp_path / "profile-v2.sqlite"
    build_wbm_target_index([
        WBMTargetRecord("wbm-a",base),
        WBMTargetRecord("wbm-b",supercell),
        WBMTargetRecord("wbm-c",alt),
    ],db, source_file_sha256="b"*64, prototype_group=_fixture_proto)
    with MPTrjWBMSourceObserver(
        db, expected_wbm_sha256="b"*64, expected_wbm_count=3,
        prototype_group=_fixture_proto,
        allow_custom_protocols_for_fixture=True,
    ) as o:
        profile=o.candidate_bucket_profile()
    assert profile["wbm_target_count"] == 3
    assert profile["composition_bucket_count"] == 2
    assert profile["composition_and_sitecount_subbucket_count"] == 3
    assert profile["composition_buckets_with_multiple_sitecounts"] == 1
    assert profile["largest_v2_composition_bucket_targets"] == 2
    assert profile["largest_v1_sitecount_subbucket_targets"] == 1
    assert profile["v2_pair_comparison_proxy"] == 5
    assert profile["v1_same_sitecount_pair_proxy"] == 3
    assert profile["mptrj_runtime_estimate_authorized"] is False
    assert profile["full_source_download_authorized"] is False


def test_v2_bucket_cap_refuses_source_fetch_even_with_positive_budget(tmp_path, monkeypatch):
    from scripts.development import run_mptrj_wbm_source_overlap as runner
    from scripts.development import verify_mptrj_remote_stream as remote
    base=Structure(Lattice.cubic(5),["Na","Cl"],[[0,0,0],[.5,.5,.5]])
    larger=base.copy()
    larger.make_supercell([2,1,1])
    db=tmp_path/"resource.sqlite"
    build_wbm_target_index([
        WBMTargetRecord("wbm-1",base),WBMTargetRecord("wbm-2",larger),
    ], db, source_file_sha256="c"*64, prototype_group=_fixture_proto)
    touched=[]
    monkeypatch.setattr(runner,"verify_remote_mptrj_full_stream",
                        lambda **kw:touched.append(True))
    with pytest.raises(ValueError,match="approved comparison cap"):
        runner.run_source_only_overlap(
            db,
            observer_options={
                "expected_wbm_sha256":"c"*64, "expected_wbm_count":2,
                "prototype_group":_fixture_proto,
                "allow_custom_protocols_for_fixture":True,
            },
            max_targets_per_composition_bucket=1,
        )
    assert touched == []


@pytest.mark.parametrize("limit", [0, -1, True, 0.5, "2"])
def test_v2_resource_cap_requires_positive_integer(tmp_path, limit):
    from scripts.development import run_mptrj_wbm_source_overlap as runner
    db,raw,opts=fixture(tmp_path)
    with pytest.raises(ValueError,match="positive explicit"):
        runner.run_source_only_overlap(
            db, observer_options=opts,
            max_targets_per_composition_bucket=limit,
        )


def test_full_download_cli_requires_explicit_bucket_cap_before_network(tmp_path,monkeypatch):
    from scripts.development import run_mptrj_wbm_source_overlap as runner
    touched=[]
    monkeypatch.setattr(runner,"verify_remote_mptrj_full_stream",
                        lambda **kw:touched.append(True))
    assert runner.main([
        "--execute-full-download",
        "--wbm-target-db",str(tmp_path/"missing.sqlite"),
        "--report",str(tmp_path/"report.json"),
    ]) == 1
    assert touched == []
