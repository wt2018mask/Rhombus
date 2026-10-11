"""0145 real OBELiX TRAIN CIF screening and pinned MACE-MPA-0 CPU inference.

A source-bound experimental record and a successful atomistic energy/force call
do NOT constitute a scored experimental ionic conductivity measurement.
Public official TEST structures are never parsed or passed to model inference.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import tempfile
import shutil

from rhombus.qualification.obelix_benchmark_intake import (
    SOURCE_COMMIT, build_obelix_benchmark_intake,
)
from scripts.science.mpa0_release_binary_observation import (
    PUBLIC_SHA256, observe_mpa0_official_release_file,
)

SCHEMA = "rhombus-obelix-original-train-mace-real-inference-0145-v1"
MAX_CIF = 16 * 1024 * 1024
MAX_SELECTED = 3
MAX_ATOMS = 96
EXPECTED = (599, 478, 121, 321)
MIN_NEIGHBOR_DIST_A = 0.65


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _finite_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _geometry(checkout: Path, row: dict):
    """Original-geometry TRAIN-only parse and physically conservative screening."""
    if row["official_split"] != "TRAIN":
        raise ValueError("official TEST structure may not enter geometry parse")
    if row["source_cif_match_status"] != "Match":
        return "NOT_EXACT_MATCH", None
    relative = row["cif_relative_path"]
    if not isinstance(relative, str) or not relative.startswith("data/randomized_cifs/"):
        raise ValueError("missing approved relative CIF path")
    path = checkout / relative
    if path.is_symlink() or not path.is_file():
        raise ValueError("untrusted or absent CIF source path")
    if checkout not in path.resolve(strict=True).parents:
        raise ValueError("source CIF escaped approved checkout")
    with path.open("rb") as reader:
        raw = reader.read(MAX_CIF + 1)
    if not raw or len(raw) > MAX_CIF or sha(raw) != row["cif_content_sha256"]:
        raise ValueError("source-bound CIF length or content digest mismatch")
    from pymatgen.core import Structure
    try:
        structure = Structure.from_str(raw.decode("utf-8"), fmt="cif")
    except (ValueError, UnicodeError, TypeError, IndexError, KeyError) as exc:
        return "CIF_PARSE_FAILED", None
    if len(structure) < 2 or len(structure) > MAX_ATOMS:
        return "UNSUPPORTED_ATOM_COUNT", None
    if not all(site.is_ordered for site in structure):
        return "DISORDERED_PARTIAL_OCCUPANCY", None
    if not any(site.specie.symbol == "Li" for site in structure):
        return "NO_LITHIUM", None
    if not _finite_number(structure.volume) or structure.volume <= 1e-3:
        return "INVALID_CELL", None
    import numpy as np
    if not np.isfinite(structure.cart_coords).all() or not np.isfinite(structure.lattice.matrix).all():
        return "NONFINITE_GEOMETRY", None
    distance = structure.distance_matrix
    np.fill_diagonal(distance, float("inf"))
    if not np.isfinite(distance[np.isfinite(distance)]).all() or float(np.min(distance)) < MIN_NEIGHBOR_DIST_A:
        return "OVERLAPPING_ATOMS", None
    return "ELIGIBLE", structure


def inspect_original_train_cifs(checkout: Path, *, expected_commit=SOURCE_COMMIT, require_official=True):
    root = Path(checkout).resolve(strict=True)
    if require_official and expected_commit != SOURCE_COMMIT:
        raise ValueError("public original source commit is immutable")
    records, provenance = build_obelix_benchmark_intake(root, expected_commit=expected_commit)
    totals = (
        provenance["record_count"], provenance["official_train_count"],
        provenance["official_test_count"], provenance["available_cif_count"]
    )
    if require_official and totals != EXPECTED:
        raise ValueError("not the approved original OBELiX source population")
    reasons = Counter()
    eligible = []
    for row in records:
        if row["official_split"] == "TEST":
            reasons["OFFICIAL_TEST_RESERVED_UNPARSED"] += 1
            continue
        try:
            status, structure = _geometry(root, row)
        except (OSError, ValueError, KeyError, TypeError):
            status, structure = "CORRUPT_UNVERIFIED_SOURCE", None
        reasons[status] += 1
        if status == "ELIGIBLE":
            eligible.append((len(structure), row["source_entry_id"], row, structure))
    if sum(reasons.values()) != len(records):
        raise ValueError("source rows silently lost during geometry screening")
    eligible.sort(key=lambda x: (x[0], x[1]))
    return {
        "source_commit": provenance["source_commit"],
        "source_tree": provenance["source_tree"],
        "processed_csv_sha256": provenance["processed_csv_sha256"],
        "records_jsonl_sha256": provenance["records_jsonl_sha256"],
        "all_source_records": totals[0],
        "official_train_records": totals[1],
        "official_test_reserved_without_geometry_inference": totals[2],
        "source_linked_cifs": totals[3],
        "train_geometry_eligibility_counts": dict(sorted(reasons.items())),
        "eligible_distinct_train_source_records_NOT_independent_materials": len(eligible),
    }, eligible


def run_original_train_mace_cpu(
    checkout: Path, model: Path, output_dir: Path, *,
    expected_commit=SOURCE_COMMIT, require_official=True, max_selected=MAX_SELECTED,
):
    if type(max_selected) is not int or not 1 <= max_selected <= MAX_SELECTED:
        raise ValueError("pilot limit must be 1..3")
    output = Path(output_dir).resolve()
    root = Path(checkout).resolve(strict=True)
    if output.exists() or output == root or root in output.parents:
        raise ValueError("output must be new and outside original source")
    # Validate exact complete model before importing torch or calculating anything.
    identity = observe_mpa0_official_release_file(Path(model))
    if identity["observed_full_file_sha256"] != PUBLIC_SHA256:
        raise ValueError("wrong published model checkpoint")
    screening, eligible = inspect_original_train_cifs(
        root, expected_commit=expected_commit, require_official=require_official)
    selected = eligible[:max_selected]
    if not selected:
        raise ValueError("no original TRAIN source geometry survived physics screening")
    from mace.calculators import MACECalculator
    from pymatgen.io.ase import AseAtomsAdaptor
    import numpy as np
    calc = MACECalculator(
        model_paths=str(Path(model).resolve(strict=True)),
        device="cpu",
        default_dtype="float32",
    )
    rows = []
    for count, source_id, row, structure in selected:
        result = {
            "original_train_source_id": source_id,
            "original_cif_sha256": row["cif_content_sha256"],
            "atom_count": count,
            "measurement_kind_metadata_NOT_training_target": row["measurement_kind"],
            "energy_eV": None,
            "energy_eV_per_atom": None,
            "max_force_eV_per_A": None,
            "status": "MODEL_EXECUTION_FAILED",
            "scientific_transport_score": None,
        }
        try:
            atoms = AseAtomsAdaptor.get_atoms(structure)
            atoms.calc = calc
            energy = float(atoms.get_potential_energy())
            forces = np.asarray(atoms.get_forces(), dtype=float)
            if (
                forces.shape != (count, 3)
                or not np.isfinite(forces).all()
                or not math.isfinite(energy)
            ):
                result["status"] = "NONFINITE_MODEL_OUTPUT"
            else:
                max_force = float(np.max(np.linalg.norm(forces, axis=1)))
                if not math.isfinite(max_force):
                    result["status"] = "NONFINITE_MODEL_OUTPUT"
                else:
                    result.update(
                        energy_eV=energy,
                        energy_eV_per_atom=energy / count,
                        max_force_eV_per_A=max_force,
                        status="REAL_MODEL_SINGLEPOINT_COMPLETED",
                    )
        except (RuntimeError, ValueError, TypeError, KeyError, ArithmeticError, IndexError):
            result["status"] = "MODEL_EXECUTION_FAILED"
        rows.append(result)
    counts = Counter(row["status"] for row in rows)
    success = counts["REAL_MODEL_SINGLEPOINT_COMPLETED"]
    report = {
        "schema_version": SCHEMA,
        "scope": "OFFICIAL_OBELIX_PUBLIC_TRAIN_DIAGNOSTIC" if require_official
                 else "SYNTHETIC_SOURCE_WITH_REAL_MODEL_TEST",
        "source": screening,
        "model": {
            "publisher_binary_sha256": identity["observed_full_file_sha256"],
            "release_asset_id": identity["source_release_asset_id"],
            "inference_backend": "MACECalculator_CPU_FLOAT32",
        },
        "selection_rule": "TRAIN_EXACT_MATCH_ORDERED_LI_VALID_GEOMETRY_SORT_ATOMS_THEN_ID",
        "selected_original_train_records": len(rows),
        "actual_successful_model_singlepoint_structures": success,
        "actual_model_failure_count": len(rows) - success,
        "status_counts": dict(sorted(counts.items())),
        "records": rows,
        "experimental_conductivity_prediction_count": 0,
        "experimentally_scored_materials": 0,
        "independent_physical_materials_authenticated": None,
        "previously_sealed_new_blind_materials": 0,
        "known_MACE_training_exposure_verified": False,
        "scientific_transport_verdict": "INDETERMINATE",
        "scientific_qualification_authorized": False,
        "P0_01_status": "BLOCKED",
        "P0_02_status": "BLOCKED",
        "P0_03_status": "BLOCKED",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(dir=output.parent, prefix=".obelix-0145-"))
    try:
        (tmp / "real_mace_train_pilot.json").write_text(
            json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n",
            encoding="utf-8",
        )
        if output.exists():
            raise ValueError("output unexpectedly already exists")
        tmp.rename(output)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--obelix-checkout", required=True, type=Path)
    p.add_argument("--model-binary", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--max-selected", type=int, default=MAX_SELECTED)
    args = p.parse_args(argv)
    try:
        report = run_original_train_mace_cpu(
            args.obelix_checkout, args.model_binary, args.output_dir,
            max_selected=args.max_selected,
        )
    except (ValueError, OSError, TypeError) as exc:
        p.error(str(exc))
    print(json.dumps({
        "source_train_count": report["source"]["official_train_records"],
        "geometry_eligible_count": report["source"]["eligible_distinct_train_source_records_NOT_independent_materials"],
        "model_success": report["actual_successful_model_singlepoint_structures"],
        "model_failure": report["actual_model_failure_count"],
        "science_go": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
