"""Source-preserving identity / possible-leakage review for bulk benchmark records.

Pairs are review candidates, never automatic merges or proofs of identical
materials. OBELiX's official train/test assignment is immutable. External
LiIon rows are optional temperature-scoped diagnostic inputs and never become
part of the OBELiX official split or a qualified transport cohort.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .obelix_benchmark_intake import SCHEMA as OBELIX_SCHEMA

SCHEMA = "rhombus-measurement-identity-review-v1"
LIION_SCHEMA = "rhombus-liion-temperature-source-record-v1"
MAX_RECORDS = 50_000
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_REVIEW_PAIRS = 120_000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OBELIX_REQUIRED = frozenset((
    "schema_version", "source_dataset", "source_entry_id",
    "source_snapshot_commit", "official_split", "reported_composition",
    "reported_ionic_conductivity_text", "reported_ionic_conductivity_unit",
    "measurement_kind", "reported_temperature_scope", "reference_dois",
    "source_cif_match_status", "cif_relative_path", "cif_content_sha256",
    "source_structure_has_verified_phase_identity",
    "source_material_independence_verified", "source_training_exposure_verified",
    "qualified_transport_truth", "independently_blinded",
))
_LIION_REQUIRED = frozenset((
    "schema_version", "source_dataset", "source_record_id",
    "source_artifact_sha256", "reported_composition", "reference_dois",
    "measurement_temperature_K", "reported_ionic_conductivity_text",
    "measurement_kind",
))


def _read_input(path: Path) -> bytes:
    if path.is_symlink():
        raise ValueError("input symlink is not permitted")
    with path.open("rb") as f:
        data = f.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("input byte budget exceeded")
    return data


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise ValueError("duplicate input JSON key")
        out[k] = v
    return out


def _no_nonfinite(value: str) -> None:
    raise ValueError("nonfinite JSON numeric literal")


def _parse_json(data: bytes) -> Any:
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_object,
                          parse_constant=_no_nonfinite)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid UTF-8 JSON") from exc


def _json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _records_from_jsonl(blob: bytes) -> list[dict[str, Any]]:
    records = []
    for line in blob.splitlines():
        if not line.strip():
            raise ValueError("empty JSONL record")
        if len(line) > 64 * 1024:
            raise ValueError("source JSONL line too large")
        row = _parse_json(line)
        if not isinstance(row, dict):
            raise ValueError("JSONL record must be object")
        records.append(row)
        if len(records) > MAX_RECORDS:
            raise ValueError("too many source records")
    return records


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value or len(value) > 256:
        raise ValueError("invalid " + label)
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError("invalid " + label)
    return value


def _dois(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 32:
        raise ValueError("invalid DOI list")
    dois = []
    for item in value:
        doi = _nonempty(item, "DOI").lower()
        if not doi.startswith("10.") or any(c.isspace() for c in doi):
            raise ValueError("invalid DOI")
        dois.append(doi)
    if len(dois) != len(set(dois)):
        raise ValueError("duplicate DOI within record")
    return tuple(dois)


def _decimal(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError("invalid " + name)
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid " + name) from exc
    if not number.is_finite() or number <= 0:
        raise ValueError("invalid " + name)
    return str(number.normalize())


def _validated(records: Sequence[Mapping[str, Any]], *, dataset: str) -> list[dict]:
    if not isinstance(records, (list, tuple)) or len(records) > MAX_RECORDS:
        raise ValueError("unsupported source record sequence")
    if dataset not in ("OBELiX", "LiIon"):
        raise ValueError("unsupported evidence source")
    seen: set[str] = set()
    out: list[dict] = []
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("source rows must be objects")
        expected = _OBELIX_REQUIRED if dataset == "OBELiX" else _LIION_REQUIRED
        if set(row) != expected:
            raise ValueError("source record schema mismatch")
        if dataset == "OBELiX":
            if row["schema_version"] != OBELIX_SCHEMA or row["source_dataset"] != dataset:
                raise ValueError("wrong OBELiX source schema")
            rid = _nonempty(row["source_entry_id"], "OBELiX ID")
            split = row["official_split"]
            if split not in ("TRAIN", "TEST"):
                raise ValueError("invalid official source split")
            if row["reported_ionic_conductivity_unit"] != "S/cm":
                raise ValueError("invalid conductivity unit")
            if row["reported_temperature_scope"] != "ROOM_TEMPERATURE_EXACT_K_UNSPECIFIED":
                raise ValueError("invalid OBELiX temperature scope")
            for flag in ("source_structure_has_verified_phase_identity",
                         "source_material_independence_verified",
                         "source_training_exposure_verified", "qualified_transport_truth",
                         "independently_blinded"):
                if row[flag] is not False:
                    raise ValueError("unverified OBELiX truth cannot be promoted")
            if row["source_cif_match_status"] not in ("Match", "Close Match", "No Match"):
                raise ValueError("invalid CIF match status")
            path, cif_sha = row["cif_relative_path"], row["cif_content_sha256"]
            if (path is None) != (cif_sha is None):
                raise ValueError("CIF path/hash mismatch")
            if (path is None) != (row["source_cif_match_status"] == "No Match"):
                raise ValueError("CIF match does not agree with source path")
            if path is not None:
                _nonempty(path, "CIF source path")
                _sha(cif_sha, "CIF source hash")
            _nonempty(row["source_snapshot_commit"], "source commit")
        else:
            if row["schema_version"] != LIION_SCHEMA or row["source_dataset"] != dataset:
                raise ValueError("wrong LiIon diagnostic schema")
            rid = _nonempty(row["source_record_id"], "LiIon ID")
            _sha(row["source_artifact_sha256"], "LiIon source artifact")
            _decimal(row["measurement_temperature_K"], "measured temperature")
            split = "SEPARATE_LIION_SOURCE"
        if rid in seen:
            raise ValueError("duplicate identity within " + dataset)
        seen.add(rid)
        _nonempty(row["reported_composition"], "reported composition")
        if row["measurement_kind"] not in ("PROCESSED_REPORTED_POINT", "UPPER_BOUND"):
            raise ValueError("invalid measurement type")
        raw = row["reported_ionic_conductivity_text"]
        if not isinstance(raw, str):
            raise ValueError("invalid conductivity text")
        _decimal(raw[1:].strip() if row["measurement_kind"] == "UPPER_BOUND"
                 and raw.startswith("<") else raw, "conductivity")
        if raw.startswith("<") != (row["measurement_kind"] == "UPPER_BOUND"):
            raise ValueError("measurement qualifier is inconsistent")
        dois = _dois(row["reference_dois"])
        name = dataset + ":" + rid
        out.append({
            "identity": name,
            "source_dataset": dataset,
            "source_id": rid,
            "split": split,
            "reported_composition": row["reported_composition"],
            "dois": dois,
            "cif_sha256": row["cif_content_sha256"] if dataset == "OBELiX" else None,
            "temperature_scope": (
                row["reported_temperature_scope"] if dataset == "OBELiX"
                else "K:" + _decimal(row["measurement_temperature_K"], "temperature")
            ),
        })
    return out


def review_measurement_identity(
    obelix_records: list[dict],
    *,
    obelix_summary: Mapping[str, Any],
    liion_records: list[dict] | None = None,
) -> tuple[list[dict], dict]:
    """Return pairwise *signals*, never inferred independent-material IDs."""
    if not isinstance(obelix_summary, Mapping):
        raise ValueError("OBELiX summary required")
    if (obelix_summary.get("schema_version") != OBELIX_SCHEMA
            or obelix_summary.get("source_kind") != "PINNED_OFFICIAL_OBELIX_PROCESSED_CSV"
            or type(obelix_summary.get("record_count")) is not int
            or obelix_summary["record_count"] != len(obelix_records)):
        raise ValueError("unbound OBELiX source summary")
    entries = _validated(obelix_records, dataset="OBELiX")
    if (obelix_summary.get("official_train_count")
            != sum(x["split"] == "TRAIN" for x in entries)
            or obelix_summary.get("official_test_count")
            != sum(x["split"] == "TEST" for x in entries)):
        raise ValueError("official OBELiX split counts changed")
    canonical_blob = b"".join(_json_bytes(x) + b"\n" for x in obelix_records)
    if (obelix_summary.get("records_jsonl_sha256") !=
            hashlib.sha256(canonical_blob).hexdigest()):
        raise ValueError("OBELiX records differ from frozen 0127 report")
    optional_liion = [] if liion_records is None else liion_records
    entries += _validated(optional_liion, dataset="LiIon")
    if len(entries) > MAX_RECORDS:
        raise ValueError("combined review exceeds record budget")
    by_identity = {x["identity"]: x for x in entries}
    index: dict[str, dict[str, list[str]]] = {
        "EXACT_REPORTED_COMPOSITION": defaultdict(list),
        "SAME_REFERENCE_DOI": defaultdict(list),
        "IDENTICAL_CIF_FILE_BYTES": defaultdict(list),
    }
    for row in entries:
        index["EXACT_REPORTED_COMPOSITION"][row["reported_composition"]].append(row["identity"])
        for doi in row["dois"]:
            index["SAME_REFERENCE_DOI"][doi].append(row["identity"])
        if row["cif_sha256"] is not None:
            index["IDENTICAL_CIF_FILE_BYTES"][row["cif_sha256"]].append(row["identity"])

    candidates: dict[tuple[str, str], set[str]] = {}
    for signal, buckets in index.items():
        for keys in buckets.values():
            ids = sorted(set(keys))
            count = len(ids) * (len(ids) - 1) // 2
            if count > MAX_REVIEW_PAIRS:
                raise ValueError("one evidence bucket exceeds pairwise review budget")
            for i, left in enumerate(ids):
                for right in ids[i + 1:]:
                    key = (left, right)
                    if key not in candidates and len(candidates) >= MAX_REVIEW_PAIRS:
                        raise ValueError("review candidate budget exceeded")
                    candidates.setdefault(key, set()).add(signal)

    results: list[dict] = []
    counter = Counter()
    for (a, b), signals in sorted(candidates.items()):
        x, y = by_identity[a], by_identity[b]
        cross_dataset = x["source_dataset"] != y["source_dataset"]
        cross_split = (
            not cross_dataset and x["source_dataset"] == "OBELiX"
            and x["split"] != y["split"]
        )
        if cross_split:
            alert = "PUBLIC_OFFICIAL_SPLIT_POTENTIAL_LEAKAGE"
        elif cross_dataset:
            alert = "CROSS_SOURCE_POSSIBLE_OVERLAP"
        else:
            alert = "WITHIN_SOURCE_REVIEW"
        counts = sorted(signals)
        counter[alert] += 1
        for signal in counts:
            counter[signal] += 1
        results.append({
            "left_source_identity": a,
            "right_source_identity": b,
            "left_original_split": x["split"],
            "right_original_split": y["split"],
            "left_reported_temperature_scope": x["temperature_scope"],
            "right_reported_temperature_scope": y["temperature_scope"],
            "signals": counts,
            "review_class": alert,
            "same_reported_temperature_scope": (
                x["temperature_scope"] == y["temperature_scope"]),
            "material_identity_resolved": False,
            "merge_authorized": False,
        })

    result_blob = b"".join(_json_bytes(x) + b"\n" for x in results)
    source_counts = Counter(x["source_dataset"] for x in entries)
    summary = {
        "schema_version": SCHEMA,
        "obelix_records_sha256": obelix_summary["records_jsonl_sha256"],
        "review_pairs_sha256": hashlib.sha256(result_blob).hexdigest(),
        "source_record_counts": {
            "OBELiX": source_counts["OBELiX"],
            "LiIon": source_counts["LiIon"],
        },
        "identity_review_pair_count": len(results),
        "overlap_signal_counts": {
            name: counter[name] for name in (
                "EXACT_REPORTED_COMPOSITION", "SAME_REFERENCE_DOI",
                "IDENTICAL_CIF_FILE_BYTES",
            )
        },
        "cross_official_split_potential_overlap_pairs": counter[
            "PUBLIC_OFFICIAL_SPLIT_POTENTIAL_LEAKAGE"
        ],
        "cross_source_potential_overlap_pairs": counter[
            "CROSS_SOURCE_POSSIBLE_OVERLAP"
        ],
        "absence_of_overlap_signal_proves_independence": False,
        "independent_material_count": None,
        "qualified_transport_material_count": None,
        "externally_blinded_material_count": 0,
        "scientific_verdict": "INDETERMINATE",
        "scientific_qualification_authorized": False,
        "limitations": [
            "EXACT_FORMULA_STRING_CAN_HIDE_PHASE_SITE_OR_DOPING_DIFFERENCES",
            "SAME_DOI_CAN_COVER_DIFFERENT_COMPOSITIONS_AND_MEASUREMENTS",
            "EXACT_CIF_FILE_HASH_DOES_NOT_PROVE_MEASURED_SAMPLE_IDENTITY",
            "ABSENT_PAIRWISE_SIGNAL_DOES_NOT_PROVE_DIFFERENT_MATERIALS",
            "PAIRWISE_OVERLAP_IS_NOT_TRANSITIVE_MATERIAL_EQUIVALENCE",
            "OBELIX_PUBLIC_OFFICIAL_SPLIT_NOT_NEW_BLIND_COHORT",
            "LIION_TEMPERATURE_RECORDS_ARE_SEPARATE_NOT_MERGED",
            "LIION_OPTIONAL_SOURCE_ROWS_NOT_INDEPENDENTLY_ATTESTED",
            "MODEL_TRAINING_EXPOSURE_AND_EXPERIMENTAL_TRUTH_UNVERIFIED",
        ],
    }
    return results, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--obelix-records-jsonl", required=True, type=Path)
    parser.add_argument("--obelix-summary-json", required=True, type=Path)
    parser.add_argument("--liion-records-jsonl", type=Path,
                        help="Optional independently supplied temperature-scoped diagnostic rows")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    inputs = [args.obelix_records_jsonl, args.obelix_summary_json]
    if args.liion_records_jsonl is not None:
        inputs.append(args.liion_records_jsonl)
    try:
        obelix_raw = _read_input(inputs[0])
        summary_raw = _read_input(inputs[1])
        obelix = _records_from_jsonl(obelix_raw)
        prior_summary = _parse_json(summary_raw)
        optional = (_records_from_jsonl(_read_input(inputs[2]))
                    if len(inputs) > 2 else None)
        results, summary = review_measurement_identity(
            obelix, obelix_summary=prior_summary, liion_records=optional)
        output = args.output_dir.resolve()
        if any(p.resolve() == output or output in p.resolve().parents for p in inputs):
            raise ValueError("output may not replace source evidence")
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise ValueError("output directory must be empty")
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    output.mkdir(parents=True, exist_ok=True)
    (output / "review_pairs.jsonl").write_bytes(
        b"".join(_json_bytes(x) + b"\n" for x in results))
    (output / "summary.json").write_bytes(_json_bytes(summary) + b"\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
