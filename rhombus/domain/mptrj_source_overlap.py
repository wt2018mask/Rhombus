"""Full-source-gated MPTrj original↔WBM overlap diagnostic, NOT training exposure."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from urllib.parse import quote

from pymatgen.core import Structure

from .mptrj import MPTrjFrame
from .structure_protocols import (
    CANDIDATE_FINGERPRINT_PROTOCOL_ID, PROTOTYPE_GROUP_PROTOCOL_ID,
    structure_candidate_fingerprint_sha256, matbench_prototype_group,
    strict_structure_equivalent, near_duplicate_structure,
)

WBM_SHA256 = "98d545172c1ea9060f03f40cace6f8173a4ac06f1ee875ccd963765211519b58"
WBM_COUNT = 256_963


class SourceOverlapError(ValueError):
    """MPTrj/WBM source-only evidence or target index invalid."""


class MPTrjWBMSourceObserver:
    """Never describes source overlap as MACE-MPA-0 *training* membership."""

    def __init__(self, db_path: Path, *, expected_wbm_sha256: str = WBM_SHA256,
                 expected_wbm_count: int = WBM_COUNT,
                 fingerprint=structure_candidate_fingerprint_sha256,
                 prototype_group=matbench_prototype_group,
                 strict_match=strict_structure_equivalent,
                 near_match=near_duplicate_structure):
        if db_path.is_symlink() or not db_path.is_file():
            raise SourceOverlapError("preexisting WBM SQLite target index required")
        uri = "file:" + quote(str(db_path.resolve()), safe="/") + "?mode=ro"
        self.db = sqlite3.connect(uri, uri=True)
        try:
            meta = dict(self.db.execute("SELECT key, value FROM metadata"))
            count = self.db.execute("SELECT COUNT(*) FROM targets").fetchone()[0]
            if (meta.get("comparison_scope") != "WBM_INITIAL_STRUCTURES"
                    or meta.get("source_file_sha256") != expected_wbm_sha256
                    or type(expected_wbm_count) is not int
                    or count != expected_wbm_count or meta.get("row_count") != str(count)):
                raise SourceOverlapError("WBM index source identity/row count not frozen")
            self.fingerprints = set(row[0] for row in self.db.execute(
                "SELECT DISTINCT candidate_fingerprint_sha256 FROM targets"
            ))
            self.prototypes = set(row[0] for row in self.db.execute(
                "SELECT DISTINCT prototype_group FROM targets"
            ))
        except BaseException:
            self.db.close()
            raise
        self.fingerprint = fingerprint
        self.prototype_group = prototype_group
        self.strict_match = strict_match
        self.near_match = near_match
        self.wbm_sha256 = expected_wbm_sha256
        self.wbm_count = count
        self.frames = 0
        self.candidate_frames = 0
        self.strict_ids = set()
        self.near_ids = set()
        self.prototype_seen = set()
        # First fully parsed MPTrj frame whose strict/near/prototype decision
        # supports each positive WBM target. Witnesses are RFC6901 locators,
        # not copies of training frames or evidence of model exposure.
        self.strict_witness = {}
        self.near_witness = {}
        self.prototype_witness = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    def observe(self, frame: MPTrjFrame) -> None:
        if not isinstance(frame, MPTrjFrame):
            raise SourceOverlapError("one fully parsed original MPTrj frame required")
        self.frames += 1
        group = self.prototype_group(frame.structure)
        if group in self.prototypes:
            self.prototype_seen.add(group)
            self.prototype_witness.setdefault(group, frame.source_locator)
        fingerprint = self.fingerprint(frame.structure)
        if fingerprint not in self.fingerprints:
            return
        self.candidate_frames += 1
        for material_id, structure_json in self.db.execute(
            "SELECT material_id, structure_json FROM targets WHERE candidate_fingerprint_sha256 = ?",
            (fingerprint,),
        ):
            material_id = str(material_id)
            if material_id in self.strict_ids and material_id in self.near_ids:
                continue
            target = Structure.from_dict(json.loads(structure_json))
            if material_id not in self.strict_ids and self.strict_match(target, frame.structure):
                self.strict_ids.add(material_id)
                self.strict_witness.setdefault(material_id, frame.source_locator)
            if material_id not in self.near_ids and self.near_match(target, frame.structure):
                self.near_ids.add(material_id)
                self.near_witness.setdefault(material_id, frame.source_locator)

    def verified_source_summary(self, full_report: dict) -> dict:
        """Caller must have completed original-byte/MD5/frame verification."""
        src = full_report.get("source_identity", {})
        cov = full_report.get("frame_coverage", {})
        model = full_report.get("model_training_lineage", {})
        if (src.get("figshare_md5_matched") is not True
                or type(cov.get("parsed_frames")) is not int
                or cov["parsed_frames"] != self.frames
                or cov.get("complete_json_consumed") is not True
                or cov.get("declared_frame_count_matched") is not True
                or model.get("exact_mace_mpa0_training_frame_selection") != "UNATTESTED"):
            raise SourceOverlapError("full original stream identity required; no partial report")
        if not isinstance(src.get("computed_sha256"), str) or len(src["computed_sha256"]) != 64:
            raise SourceOverlapError("missing locally computed full-source SHA256")
        prototype_count = 0
        for group in self.prototype_seen:
            prototype_count += self.db.execute(
                "SELECT COUNT(*) FROM targets WHERE prototype_group = ?", (group,),
            ).fetchone()[0]
        return {
            "schema_version": "rhombus-mptrj-wbm-original-source-overlap-v1",
            "status": "SOURCE_ONLY_NOT_MACE_MPA0_TRAINING_SET",
            "mptrj_canonical_source_sha256": src["computed_sha256"],
            "mptrj_complete_frames": self.frames,
            "wbm_initial_source_sha256": self.wbm_sha256,
            "wbm_initial_structure_count": self.wbm_count,
            "candidate_mptrj_frames": self.candidate_frames,
            "wbm_structures_strict_mptrj_source_match": len(self.strict_ids),
            "wbm_structures_near_mptrj_source_match": len(self.near_ids),
            "wbm_structures_prototype_mptrj_source_overlap": prototype_count,
            "fingerprint_protocol_id": CANDIDATE_FINGERPRINT_PROTOCOL_ID,
            "prototype_protocol_id": PROTOTYPE_GROUP_PROTOCOL_ID,
            "exact_mace_mpa0_training_membership_attested": False,
            "execute_training_exposure_audit": False,
            "unseen_generalization_claim": False,
            "empirical_calibration_use": False,
        }


    def iter_verified_matched_targets(self, full_report: dict):
        """Yield only *positive source-only* WBM matches in stable ID order.

        Absence from this sequence does NOT mean a WBM material is unseen by
        MACE-MPA-0 or safe for domain calibration. The generator performs a
        complete original-source verification preflight before emitting rows,
        never yields source structure payloads, and is bounded by WBM targets.
        """
        summary = self.verified_source_summary(full_report)
        for material_id, group in self.db.execute(
            "SELECT material_id, prototype_group FROM targets ORDER BY material_id"
        ):
            material_id = str(material_id)
            strict = material_id in self.strict_ids
            near = material_id in self.near_ids
            prototype = str(group) in self.prototype_seen
            if strict or near or prototype:
                yield {
                    "record_type": "WBM_ORIGINAL_MPTRJ_SOURCE_MATCH",
                    "material_id": material_id,
                    "strict_original_source_structure_match": strict,
                    "near_original_source_structure_match": near,
                    "original_source_prototype_overlap": prototype,
                    "strict_source_frame_locator": self.strict_witness.get(material_id) if strict else None,
                    "near_source_frame_locator": self.near_witness.get(material_id) if near else None,
                    "prototype_source_frame_locator": self.prototype_witness.get(str(group)) if prototype else None,
                    "mptrj_source_sha256": summary["mptrj_canonical_source_sha256"],
                    "wbm_initial_source_sha256": self.wbm_sha256,
                    "model_training_membership_attested": False,
                    "unseen_generalization_claim": False,
                }
