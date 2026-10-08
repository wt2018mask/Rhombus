"""Offline bounded MPTrj multi-frame prefix inspection against a REAL frozen anchor.

Only COMPLETE validated frames are emitted; the remaining source is UNVERIFIED.
No Figshare or GitHub requests, source persistence, or scientific gate opening.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import hmac
import io
import json
from pathlib import Path
import sys

import ijson
from pymatgen.core import Structure

from rhombus.domain.mptrj import (
    MPTrjFormatError, _read_frame, _require_id, _locator_component,
)
from rhombus.domain.mptrj_energy_labels import inspect_mptrj_frame_energy_labels
from scripts.development.probe_mptrj_source_prefix import (
    DEFAULT_PREFIX_BYTES, MAX_PREFIX_BYTES, PrefixProbeError,
)
from scripts.development.reobserve_mptrj_frozen_prefix import read_frozen_first_frame

CAPTURE_SIZES = (DEFAULT_PREFIX_BYTES, MAX_PREFIX_BYTES)
MAX_COMPLETE_FRAMES = 16
MAX_MATERIAL_KEYS = 16


class MPTrjMultiFrameError(ValueError):
    """Invalid frozen baseline, MPTrj source prefix, or bounded frame metadata."""


def _summarize_frame(material_id: str, frame_id: str, frame: dict) -> dict:
    serialized = frame.get("structure")
    if not isinstance(serialized, dict):
        raise MPTrjMultiFrameError("complete frame lacks serialized Structure object")
    try:
        structure = Structure.from_dict(serialized)
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        raise MPTrjMultiFrameError("invalid pymatgen Structure in complete frame") from exc
    if not 1 <= len(structure) <= 100_000:
        raise MPTrjMultiFrameError("complete frame Structure has invalid site count")
    energy = inspect_mptrj_frame_energy_labels(frame)
    return {
        "material_id": material_id,
        "frame_id": frame_id,
        "source_locator": "/" + "/".join(
            (_locator_component(material_id), _locator_component(frame_id))
        ),
        "site_count": len(structure),
        "reduced_formula": structure.composition.element_composition.reduced_formula,
        "energy_fields_present": {
            "uncorrected_total_energy": energy.raw_vasp_total_energy_ev is not None,
            "corrected_total_energy": energy.mp2020_corrected_total_energy_ev is not None,
            "energy_per_atom": energy.chgnet_mp2020_corrected_energy_per_atom_ev is not None,
        },
        "complete_frame_parsed": True,
    }


def _parse_complete_frames(prefix: bytes, *, max_frames: int) -> tuple[list[dict], str]:
    """Parse only whole frames in an initial bounded MPTrj nested mapping.

    Prefix end, including one incomplete final frame or truncated JSON token,
    never proves full source validity. Malformed complete frames and duplicates
    fail closed, even if an earlier full frame was already parsed.
    """
    if type(max_frames) is not int or not 1 <= max_frames <= MAX_COMPLETE_FRAMES:
        raise MPTrjMultiFrameError("max complete frames exceeds 16-frame budget")
    events = iter(ijson.basic_parse(io.BytesIO(prefix), use_float=True))
    rows: list[dict] = []
    materials: set[str] = set()

    def item(expected: str, label: str):
        try:
            event, value = next(events)
        except StopIteration as exc:
            raise MPTrjFormatError("truncated MPTrj JSON at " + label) from exc
        if event != expected:
            raise MPTrjMultiFrameError("invalid nested JSON layout at " + label)
        return value

    def observed_tail(kind: str) -> tuple[list[dict], str]:
        if not rows:
            raise MPTrjMultiFrameError("no complete first frame was established")
        return rows, kind

    try:
        item("start_map", "root")
        while True:
            root_event, root_value = next(events)
            if root_event == "end_map":
                return observed_tail("ROOT_MAPPING_CLOSED_WITHIN_PREFIX_NOT_FULL_SOURCE")
            if root_event != "map_key":
                raise MPTrjMultiFrameError("unexpected MPTrj material entry")
            material = _require_id(root_value, "material_id")
            if material in materials:
                raise MPTrjMultiFrameError("duplicate material ID in bounded prefix")
            materials.add(material)
            if len(materials) > MAX_MATERIAL_KEYS:
                raise MPTrjMultiFrameError("bounded prefix exceeds material-key cap")
            item("start_map", "material mapping")
            frame_ids: set[str] = set()
            while True:
                event, value = next(events)
                if event == "end_map":
                    break
                if event != "map_key":
                    raise MPTrjMultiFrameError("unexpected MPTrj frame entry")
                frame_id = _require_id(value, "frame_id")
                if frame_id in frame_ids:
                    raise MPTrjMultiFrameError("duplicate frame ID in bounded prefix")
                frame_ids.add(frame_id)
                item("start_map", "frame")
                try:
                    frame = _read_frame(
                        events,
                        max_frame_events=150_000,
                        max_frame_scalar_chars=MAX_PREFIX_BYTES,
                    )
                except MPTrjFormatError as exc:
                    if "truncated MPTrj JSON" in str(exc):
                        return observed_tail("TAIL_UNVERIFIED_FRAME_INCOMPLETE_OR_INVALID")
                    raise
                rows.append(_summarize_frame(material, frame_id, frame))
                if len(rows) == max_frames:
                    return rows, "FRAME_CAP_REACHED_TAIL_NOT_INSPECTED"
    except (StopIteration, ijson.JSONError, UnicodeError, OverflowError) as exc:
        return observed_tail("TAIL_UNVERIFIED_TRUNCATED_OR_MALFORMED")
    except MPTrjFormatError as exc:
        if "truncated MPTrj JSON" in str(exc):
            return observed_tail("TAIL_UNVERIFIED_TRUNCATED_OR_MALFORMED")
        raise MPTrjMultiFrameError(str(exc)) from exc


def inspect_mptrj_capped_prefix(
    prefix: bytes, *, max_frames: int = MAX_COMPLETE_FRAMES,
    frozen_receipt: dict | None = None,
) -> dict:
    """Admit complete frames ONLY if original real 256KiB prefix hash agrees."""
    if not isinstance(prefix, bytes) or len(prefix) not in CAPTURE_SIZES:
        raise MPTrjMultiFrameError("sample must be exactly 256KiB or 1MiB")
    if frozen_receipt is None:
        frozen_receipt = read_frozen_first_frame()
    frozen = frozen_receipt["observation"]
    current_digest = sha256(prefix[:DEFAULT_PREFIX_BYTES]).hexdigest()
    if not hmac.compare_digest(current_digest, frozen["prefix_sha256"]):
        raise MPTrjMultiFrameError("first 256KiB does not match frozen real observed source SHA256")
    frames, tail = _parse_complete_frames(prefix, max_frames=max_frames)
    first = frames[0]
    expected = frozen["first_frame_structure"]
    for key in ("material_id", "frame_id", "site_count", "reduced_formula", "energy_fields_present"):
        if first[key] != expected[key]:
            raise MPTrjMultiFrameError("first complete frame differs from frozen observation: " + key)
    return {
        "schema_version": "rhombus-phase3-mptrj-bounded-multiframe-diagnostic-v1",
        "status": "SAMPLED_FRAMES_ONLY_SOURCE_AND_TRAINING_UNATTESTED",
        "source_file_id": 41619375,
        "frozen_first_256k_sha256": current_digest,
        "sample_bytes": len(prefix),
        "sample_sha256": sha256(prefix).hexdigest(),
        "complete_frame_count": len(frames),
        "complete_frames": frames,
        "tail_status": tail,
        "original_full_source_verified": False,
        "training_selected_frames_attested": False,
        "model_exposure_audit_authorized": False,
        "empirical_calibration_authorized": False,
        "unseen_generalization_claim_authorized": False,
    }


def inspect_local_mptrj_prefix(*, sample: Path, max_frames: int = MAX_COMPLETE_FRAMES) -> dict:
    """Zero-network, zero-write admission of caller-supplied bounded raw sample."""
    if sample.is_symlink() or not sample.is_file():
        raise MPTrjMultiFrameError("sample must be a regular non-symlink file")
    if sample.stat().st_size not in CAPTURE_SIZES:
        raise MPTrjMultiFrameError("sample length is not one of the frozen bounded sizes")
    with sample.open("rb") as source:
        prefix = source.read(MAX_PREFIX_BYTES + 1)
    return inspect_mptrj_capped_prefix(prefix, max_frames=max_frames)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", required=True, type=Path)
    parser.add_argument("--max-frames", type=int, default=MAX_COMPLETE_FRAMES)
    args = parser.parse_args(argv)
    try:
        evidence = inspect_local_mptrj_prefix(sample=args.sample, max_frames=args.max_frames)
    except (ValueError, OSError, UnicodeError, TypeError, OverflowError, ijson.JSONError) as exc:
        print(f"MPTRJ_BOUNDED_MULTIFRAME_REJECTED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(evidence, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
