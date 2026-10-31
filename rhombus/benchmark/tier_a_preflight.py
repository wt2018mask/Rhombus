"""0204 Tier-A LiTraj *draft* group preflight without energy target access.

This module is a metadata-only preparation surface. It never reads energy-bearing
XYZ files, decodes index target tokens, calculates errors, or authorizes runs.
The owner-provided ZIP SHA256 establishes byte continuity, not publisher
cryptographic authenticity. LiTraj chemsys groups are not independent sources.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence
import json
import re
import zipfile

ZIP_BYTES = 68_583_182
ZIP_SHA256 = "b7a99d89337902e9e1da319f57547170fdb132bf15bf6ffef03a0140e2207d7f"
INDEX_MEMBER = "nebDFT2k/nebDFT2k_index.csv"
INDEX_HEADER = b"material_id,edge_id,chemsys,has_specific_TM,em_bvse,em_dft,_split"
SPLITS = ("train", "val", "test")
MAX_INDEX_BYTES = 1_000_000
MAX_METADATA_ROWS = 10_000
PILOT_SEED = "RHOMBUS_0204_TIERA_TINY_METADATA_PILOT_V1"
SCHEMA = "rhombus-0204-tier-a-metadata-preflight-draft-v1"
OWNER_ASSERTION = "OWNER_SUPPLIED_BYTE_CONTINUITY_NOT_PUBLISHER_AUTHENTICATION"
FIELDS = ("material_id", "edge_id", "chemsys", "has_specific_TM", "published_split")


def _digest(payload: Any) -> str:
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True).encode("ascii")).hexdigest()


def _check_row(row: Mapping[str, str]) -> None:
    if type(row) is not dict or set(row) != set(FIELDS):
        raise ValueError("NON_ALLOWLIST_METADATA_FIELD")
    material, edge, chem, tm, split = (row[f] for f in FIELDS)
    if any(type(value) is not str for value in (material, edge, chem, tm, split)):
        raise ValueError("INVALID_METADATA_TYPE")
    if not re.fullmatch(r"mp-[0-9]+", material) or not re.fullmatch(
        r"mp-[0-9]+_[0-9_-]+", edge
    ) or not edge.startswith(material + "_"):
        raise ValueError("INVALID_SOURCE_ID")
    if not re.fullmatch(r"[A-Z][a-z]?(?:-[A-Z][a-z]?)*", chem):
        raise ValueError("INVALID_CHEMSYS")
    elements = chem.split("-")
    if len(set(elements)) != len(elements) or "Li" not in elements:
        raise ValueError("INVALID_CHEMSYS")
    if chem != "-".join(sorted(elements)):
        raise ValueError("NON_CANONICAL_CHEMSYS")
    if tm not in ("True", "False") or split not in SPLITS:
        raise ValueError("INVALID_SPLIT_OR_TM_FIELD")


def parse_index_allowlist(blob: bytes) -> list[dict[str, str]]:
    """Decode ONLY index fields [0,1,2,3,6]; target tokens [4,5] remain opaque.

    Raw line buffers necessarily contain target bytes due to CSV layout. No
    target token is decoded or sent to a report, debug log or return value.
    Requires the exact unquoted 7-column publisher format, and fails closed on
    CSV dialect ambiguity instead of invoking a generic CSV decoder.
    """
    if type(blob) is not bytes or len(blob) > MAX_INDEX_BYTES:
        raise ValueError("INDEX_BYTE_BUDGET_OR_TYPE")
    lines = blob.splitlines()
    if not lines or lines[0].rstrip(b"\r") != INDEX_HEADER:
        raise ValueError("UNSAFE_OR_UNKNOWN_INDEX_SCHEMA")
    if not 2 <= len(lines) <= MAX_METADATA_ROWS + 1:
        raise ValueError("INVALID_INDEX_ROW_COUNT")
    rows: list[dict[str, str]] = []
    seen_edges: set[str] = set()
    material_split: dict[str, str] = {}
    for line in lines[1:]:
        if len(line) > 2048 or b'"' in line or b"\x00" in line:
            raise ValueError("AMBIGUOUS_CSV_ENCODING")
        tokens = line.rstrip(b"\r").split(b",")
        if len(tokens) != 7:
            raise ValueError("UNEXPECTED_INDEX_FIELD_COUNT")
        try:
            # Deliberately do not decode, parse, compare or log tokens[4:6].
            material, edge, chem, tm, split = (
                tokens[j].decode("ascii") for j in (0, 1, 2, 3, 6)
            )
        except UnicodeDecodeError as exc:
            raise ValueError("NON_ASCII_METADATA") from exc
        chem = "-".join(sorted(chem.split("-")))
        row = dict(zip(FIELDS, (material, edge, chem, tm, split)))
        _check_row(row)
        if edge in seen_edges:
            raise ValueError("DUPLICATE_EDGE_ID")
        if material in material_split and material_split[material] != split:
            raise ValueError("MATERIAL_CROSSES_PUBLISHED_SPLIT")
        seen_edges.add(edge)
        material_split[material] = split
        rows.append(row)
    return rows


def _file_sha256(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_verified_owner_index(archive: Path) -> list[dict[str, str]]:
    """Open just the index. SHA verification scans compressed bytes, not XYZ data.

    No whole-archive CRC recheck is performed. This is owner-byte continuity
    only; a matching SHA is not proof of independent publisher authenticity.
    """
    archive = Path(archive)
    if archive.stat().st_size != ZIP_BYTES or _file_sha256(archive) != ZIP_SHA256:
        raise ValueError("OWNER_ARCHIVE_IDENTITY_MISMATCH")
    with zipfile.ZipFile(archive) as z:
        matches = [i for i in z.infolist() if i.filename == INDEX_MEMBER]
        if len(matches) != 1 or matches[0].is_dir():
            raise ValueError("INDEX_MISSING_OR_DUPLICATED")
        if matches[0].file_size > MAX_INDEX_BYTES:
            raise ValueError("INDEX_DECOMPRESSION_BUDGET")
        with z.open(matches[0]) as f:
            blob = f.read(MAX_INDEX_BYTES + 1)
    return parse_index_allowlist(blob)


def _checked_rows(rows: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    if not isinstance(rows, (list, tuple)) or not 3 <= len(rows) <= MAX_METADATA_ROWS:
        raise ValueError("INVALID_METADATA_UNIVERSE")
    edges: set[str] = set()
    mat_splits: dict[str, str] = {}
    copy = []
    for row in rows:
        _check_row(row)
        if row["edge_id"] in edges:
            raise ValueError("DUPLICATE_EDGE_ID")
        m, s = row["material_id"], row["published_split"]
        if m in mat_splits and mat_splits[m] != s:
            raise ValueError("MATERIAL_CROSSES_PUBLISHED_SPLIT")
        mat_splits[m] = s
        edges.add(row["edge_id"])
        copy.append(dict(row))
    if any(not any(r["published_split"] == s for r in copy) for s in SPLITS):
        raise ValueError("MISSING_PUBLISHED_SPLIT")
    return copy


def build_metadata_registry(rows: Sequence[dict[str, str]]) -> dict[str, Any]:
    """Candidate-group registry. Never reassign or access original held-out targets."""
    rows = _checked_rows(rows)
    by_group: dict[str, set[str]] = defaultdict(set)
    original_splits: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_group[row["chemsys"]].add(row["published_split"])
        original_splits[row["published_split"]].append(row)
    group_owner = {
        g: next(s for s in ("test", "val", "train") if s in memberships)
        for g, memberships in by_group.items()
    }
    registry_rows: list[dict[str, str]] = []
    kept: dict[str, list[dict[str, str]]] = {s: [] for s in SPLITS}
    for row in rows:
        origin = row["published_split"]
        allocated = group_owner[row["chemsys"]]
        candidate = origin if origin == allocated else "excluded"
        entry = dict(row, group_id="CHEMSYS:" + row["chemsys"], candidate_split=candidate)
        registry_rows.append(entry)
        if candidate != "excluded":
            kept[candidate].append(entry)
    for i, a in enumerate(SPLITS):
        for b in SPLITS[i + 1:]:
            if {x["chemsys"] for x in kept[a]} & {x["chemsys"] for x in kept[b]}:
                raise ValueError("CHEMSYS_GROUP_LEAKAGE")
    if len(kept["test"]) != len(original_splits["test"]):
        raise ValueError("TEST_NOT_PRESERVED")
    registry_rows.sort(key=lambda x: x["edge_id"])
    counts = {
        "all_edges": len(rows),
        "unique_material_ids": len({r["material_id"] for r in rows}),
        "unique_chemsys": len(by_group),
        "chemsys_across_multiple_original_splits": sum(len(splits) > 1 for splits in by_group.values()),
        "original_edges": {s: len(original_splits[s]) for s in SPLITS},
        "retained_edges": {s: len(kept[s]) for s in SPLITS},
        "retained_groups": {s: len({r["group_id"] for r in kept[s]}) for s in SPLITS},
        "excluded_edges": sum(e["candidate_split"] == "excluded" for e in registry_rows),
        "excluded_by_published_split": {s: sum(e["published_split"] == s and e["candidate_split"] == "excluded" for e in registry_rows) for s in SPLITS},
    }
    return {
        "schema_version": SCHEMA,
        "claim_scope": "TIER_A_RETROSPECTIVE_LI_HOP_ENERGY_SPAN",
        "status": "CANDIDATE_ONLY_NOT_FROZEN",
        "archive_owner_sha256": ZIP_SHA256,
        "publisher_provenance": OWNER_ASSERTION,
        "target_access": "NEVER_DECODED_OR_PARSED",
        "grouping": "CANONICAL_CHEMSYS; NOT_PROTOTYPE_OR_INDEPENDENT_SOURCE",
        "policy": "TEST_GT_VAL_GT_TRAIN_WITH_CONFLICT_PURGE; ORIGINAL_SPLIT_NEVER_MOVED",
        "counts": counts,
        "rows_sha256": _digest(registry_rows),
        "rows": registry_rows,
    }


def select_train_only_pilot(registry: Mapping[str, Any], n_groups: int = 4) -> dict[str, Any]:
    """Return exact *metadata-only* 4-group TRAIN proposal with fixed digest."""
    if type(n_groups) is not int or n_groups != 4:
        raise ValueError("ONLY_FOUR_GROUP_PILOT_DRAFT_SUPPORTED")
    if registry.get("schema_version") != SCHEMA or registry.get("status") != "CANDIDATE_ONLY_NOT_FROZEN":
        raise ValueError("INVALID_DRAFT_REGISTRY")
    rows = registry.get("rows")
    if not isinstance(rows, list) or _digest(rows) != registry.get("rows_sha256"):
        raise ValueError("REGISTRY_ROWS_HASH_MISMATCH")
    # Rebuild and recheck all grouping invariants, rather than trusting labels.
    source = [{k: row[k] for k in FIELDS} for row in rows]
    expected = build_metadata_registry(source)
    if expected["rows_sha256"] != registry["rows_sha256"] or expected["rows"] != rows:
        raise ValueError("REGISTRY_SPLIT_OR_GROUP_TAMPERED")
    by_group: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if row["candidate_split"] == "train" and row["published_split"] == "train":
            by_group[row["chemsys"]].append(row["edge_id"])
    if len(by_group) < n_groups:
        raise ValueError("TOO_FEW_INDEPENDENT_TRAIN_CHEMSYS")
    ranked_groups = sorted(by_group, key=lambda g: (_digest([PILOT_SEED, "group", g]), g))
    chosen: list[dict[str, str]] = []
    for group in ranked_groups[:n_groups]:
        edge = min(by_group[group], key=lambda e: (_digest([PILOT_SEED, "edge", group, e]), e))
        chosen.append({"edge_id": edge, "group_id": "CHEMSYS:" + group, "published_split": "train"})
    return {
        "status": "TRAIN_METADATA_PROPOSAL_NOT_RUN_NOT_AUTHORIZED",
        "sampling_seed": PILOT_SEED,
        "n_edges": n_groups,
        "registry_rows_sha256": registry["rows_sha256"],
        "selection_sha256": _digest(chosen),
        "selected": chosen,
    }


def readiness_blockers(protocol: Mapping[str, Any]) -> dict[str, Any]:
    """Read-only readiness diagnostic; NEVER an execution authorization.

    Validate exactly the pre-existing draft schema and report missing owner
    decisions. An unverified field cannot become approved merely by setting it.
    """
    if not isinstance(protocol, Mapping) or protocol.get("schema_version") != "rhombus-0204-tier-a-retrospective-energy-span-protocol-candidate-v1":
        raise ValueError("UNKNOWN_PROTOCOL_SCHEMA")
    decision = protocol.get("decision") or {}
    if (decision.get("tier_a_benchmark") != "BENCHMARK_NOT_FROZEN"
            or decision.get("tier_b") != "TIER_B_NOT_FROZEN"
            or decision.get("scientific") != "SCIENTIFIC_NO_GO_ABSTAIN"
            or decision.get("baseline_execution") != "NOT_AUTHORIZED"):
        raise ValueError("IMPROPER_SCIENTIFIC_OR_EXECUTION_PROMOTION")
    experiment = protocol.get("candidate_experiment_protocol") or {}
    dp = experiment.get("decision_policy") or {}
    if experiment.get("scoring_allowed_now") is not False or experiment.get("published_test_targets_remain_sealed") is not True:
        raise ValueError("HELDOUT_EMBARGO_OR_SCORING_FLAG_CHANGED")
    if decision.get("performance_results", "MISSING") is not None:
        raise ValueError("UNAUTHORIZED_PERFORMANCE_RESULT")
    source = protocol.get("data_reference") or {}
    if source.get("owner_supplied_sha256") != ZIP_SHA256 or source.get("archive_bytes") != ZIP_BYTES:
        raise ValueError("SOURCE_IDENTITY_CONTRACT_MISMATCH")
    if dp.get("conditional_risk_if_accepted_zero", "MISSING") is not None:
        raise ValueError("ZERO_COVERAGE_RISK_MUST_BE_UNDEFINED")
    if dp.get("delta_eV") is not None:
        raise ValueError("UNAPPROVED_DELTA_THRESHOLD")
    budget = experiment.get("equal_budget_accounting_draft") or {}
    arms = experiment.get("model_arms") or []
    if not isinstance(arms, list) or len(arms) < 2:
        raise ValueError("MISSING_STRONG_BASELINES")
    if not any(a.get("id") == "MACE_MPA_0_MEDIUM_RHOMBUS" for a in arms):
        raise ValueError("MISSING_RHOMBUS_BASELINE")
    blockers = ["OWNER_SEPARATE_COMPUTE_APPROVAL_MISSING", "DELTA_EV_UNSET", "MACE_TRAINING_EXPOSURE_UNKNOWN"]
    caps = budget.get("per_arm_per_edge_caps") or {}
    if any(caps.get(k) is None for k in ("wall_seconds", "cpu_seconds", "force_evaluations", "peak_rss_MiB")):
        blockers.append("PER_ARM_BUDGET_CAPS_UNSET")
    total = budget.get("total_pilot_caps") or {}
    if any(total.get(k) is None for k in ("wall_seconds", "cpu_seconds", "number_of_arms")):
        blockers.append("TOTAL_PILOT_BUDGET_CAPS_UNSET")
    if any(a.get("checkpoint_sha256") is None for a in arms if a.get("type") == "reference strong MLIP candidate"):
        blockers.append("CHECKPOINTS_NOT_ALL_PINNED")
    return {
        "tier_a_protocol": "TIER_A_PROTOCOL_DRAFT_READY",
        "benchmark": "BENCHMARK_NOT_FROZEN",
        "execution_authorized": False,
        "blockers": blockers,
        "note": "No settings supplied here can authorize scientific compute.",
    }


def conditional_false_acceptance_risk(*, accepted: int, severe: int) -> float | None:
    """Synthetic/count-only contract check. NOT a scoring function."""
    if type(accepted) is not int or type(severe) is not int or accepted < 0 or not 0 <= severe <= accepted:
        raise ValueError("INVALID_ACCEPTED_OR_SEVERE_COUNT")
    return None if accepted == 0 else severe / accepted
