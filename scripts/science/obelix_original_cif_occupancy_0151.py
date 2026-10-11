"""0151-B: real original TRAIN crystal occupancy/phase-admission inventory.

No official TEST crystal parsed, no disordered CIF "rounded" into a model
geometry, no physics model/transport inference, no independent paper approval.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile

from rhombus.qualification.obelix_benchmark_intake import (
    SOURCE_COMMIT, _json_bytes, build_obelix_benchmark_intake
)
from scripts.science.obelix_mace_real_cpu_pilot import (
    inspect_original_train_cifs, MAX_CIF, MAX_ATOMS, MIN_NEIGHBOR_DIST_A,
)

SCHEMA = "rhombus-original-obelix-cif-occupancy-phase-review-0151-v1"
MAX_REVIEW = 10
MAX_SITE_PARSE = 2500


def _source_verified_cif(root: Path, row: dict):
    """Read only first-party source-sha-bound matched TRAIN CIF bytes."""
    if row["official_split"] != "TRAIN":
        raise ValueError("original official TEST CIF and metadata are reserved")
    if row["source_cif_match_status"] not in ("Match", "Close Match"):
        raise ValueError("not a source reported linked CIF")
    relative = row["cif_relative_path"]
    if not isinstance(relative, str) or not relative.startswith("data/randomized_cifs/"):
        raise ValueError("CIF must be in approved original randomized directory")
    p = root / relative
    if p.is_symlink() or not p.is_file():
        raise ValueError("original source CIF missing or symlinked")
    if root not in p.resolve(strict=True).parents:
        raise ValueError("original source escaped approved checkout")
    with p.open("rb") as f:
        blob = f.read(MAX_CIF + 1)
    expected = row["cif_content_sha256"]
    if not blob or len(blob) > MAX_CIF or hashlib.sha256(blob).hexdigest() != expected:
        raise ValueError("original CIF source-bound SHA256 or size mismatch")
    return blob


def _parsed_crystal_status(raw: bytes, row: dict):
    """Parser stats; never use a disordered or close-match CIF as actual phase."""
    import numpy as np
    from pymatgen.core import Structure, Composition

    try:
        structure = Structure.from_str(raw.decode("utf-8"), fmt="cif")
    except (UnicodeError, ValueError, TypeError, IndexError, KeyError) as exc:
        return {"status": "CIF_PARSE_FAILED", "reason": type(exc).__name__}
    if not 1 <= len(structure) <= MAX_SITE_PARSE:
        return {"status": "UNSUPPORTED_PARSED_SITE_COUNT"}
    if (
        not np.isfinite(structure.lattice.matrix).all()
        or not np.isfinite(structure.cart_coords).all()
        or not math.isfinite(float(structure.volume))
        or float(structure.volume) <= 1e-3
    ):
        return {"status": "INVALID_LATTICE_OR_POSITION"}
    li_occupancy = 0.0
    fractional_sites = 0
    partial_vacancies = 0
    mixed_species_sites = 0
    site_occupancy_overfull = 0
    for site in structure:
        species = site.species
        total = float(sum(float(occupancy) for occupancy in species.values()))
        if not math.isfinite(total) or total <= 0:
            return {"status": "INVALID_SITE_OCCUPANCY"}
        if total > 1.01:
            site_occupancy_overfull += 1
        if total < 0.999:
            partial_vacancies += 1
        if not site.is_ordered:
            fractional_sites += 1
        if len(species) > 1:
            mixed_species_sites += 1
        for element, occupancy in species.items():
            if element.symbol == "Li":
                li_occupancy += float(occupancy)
    if site_occupancy_overfull:
        return {"status": "INVALID_OVERFULL_OCCUPANCY"}
    if len(structure) > 1:
        distances = structure.distance_matrix.copy()
        np.fill_diagonal(distances, np.inf)
        d = float(np.min(distances))
        if not math.isfinite(d):
            return {"status": "INVALID_INTERATOMIC_DISTANCE"}
    else:
        d = None
    try:
        declared = Composition(row["reported_composition"]).fractional_composition
        parsed = structure.composition.fractional_composition
        elements = set(declared.get_el_amt_dict()) | set(parsed.get_el_amt_dict())
        matching = all(
            abs(float(declared.get_el_amt_dict().get(el, 0.0)) -
                float(parsed.get_el_amt_dict().get(el, 0.0))) <= 0.03
            for el in elements
        )
    except (ValueError, TypeError, KeyError, ArithmeticError):
        matching = False
    disordered = fractional_sites > 0
    if li_occupancy <= 0:
        category = "NO_LITHIUM_STRUCTURE"
    elif disordered:
        category = "DISORDERED_OCCUPANCY_PRESERVED_NO_MODEL"
    elif len(structure) < 2 or len(structure) > MAX_ATOMS:
        category = "UNSUPPORTED_ATOMS_FOR_0145_MODEL"
    elif d is not None and d < MIN_NEIGHBOR_DIST_A:
        category = "OVERLAPPING_ATOMS_FOR_0145_MODEL"
    else:
        category = "ORDERED_LITHIUM_GEOMETRY_CANDIDATE"
    return {
        "status": category,
        "atomic_sites": len(structure),
        "fractional_sites": fractional_sites,
        "partial_vacancy_sites": partial_vacancies,
        "mixed_species_sites": mixed_species_sites,
        "contains_lithium": li_occupancy > 0,
        "min_neighbor_distance_A": round(d, 5) if d is not None else None,
        "volume_A3": round(float(structure.volume), 5),
        "reported_vs_parsed_fractional_formula_match_0p03": matching,
        "crystal_is_publisher_verified_experimental_phase": False,
    }


def analyze_pinned_train_cif_cohort(root: Path, *, expected_commit=SOURCE_COMMIT, require_official=True):
    source = Path(root).resolve(strict=True)
    if require_official and expected_commit != SOURCE_COMMIT:
        raise ValueError("cannot claim official B audit from synthetic revision")
    entries, provenance = build_obelix_benchmark_intake(
        source, expected_commit=expected_commit)
    if require_official and (
        provenance["record_count"], provenance["official_train_count"],
        provenance["official_test_count"], provenance["available_cif_count"]
    ) != (599, 478, 121, 321):
        raise ValueError("original pinned scientific source population drift")
    counters = Counter()
    combinations = Counter()
    rows = []
    for row in entries:
        if row["official_split"] == "TEST":
            # Must not access official TEST content, CIF, DOI, formula or label.
            counters["OFFICIAL_PUBLIC_TEST_RESERVED_UNREAD"] += 1
            continue
        counters["ORIGINAL_PUBLIC_TRAIN"] += 1
        status = row["source_cif_match_status"]
        counters["TRAIN_CIF_" + status.replace(" ", "_").upper()] += 1
        if status == "No Match":
            counters["NO_SOURCE_LINKED_CIF"] += 1
            continue
        raw = _source_verified_cif(source, row)
        detail = _parsed_crystal_status(raw, row)
        observed = detail["status"]
        counters["PARSE_" + observed] += 1
        combinations[status + "|" + observed] += 1
        if "fractional_sites" in detail:
            counters["PARSED_STRUCTURES"] += 1
            if detail["fractional_sites"]:
                counters["STRUCTURES_WITH_FRACTIONAL_SITES"] += 1
                counters["FRACTIONAL_SITE_TOTAL"] += detail["fractional_sites"]
            if detail["partial_vacancy_sites"]:
                counters["STRUCTURES_WITH_VACANCY_SITES"] += 1
            if detail["mixed_species_sites"]:
                counters["STRUCTURES_WITH_MIXED_SPECIES_SITES"] += 1
            if not detail["reported_vs_parsed_fractional_formula_match_0p03"]:
                counters["PUBLISHER_REPORTED_PARSED_COMPOSITION_MISMATCH_0P03"] += 1
        if (status == "Match" and "fractional_sites" in detail and
            detail["contains_lithium"] and
            detail["status"] not in ("INVALID_OVERFULL_OCCUPANCY",
                                    "INVALID_LATTICE_OR_POSITION")):
            rows.append({
                "source_entry_id": row["source_entry_id"],
                "source_dois": row["reference_dois"],
                "original_cif_sha256": row["cif_content_sha256"],
                "original_cif_match": "Match",
                "reason": observed,
                "fractional_site_count": detail["fractional_sites"],
                "reported_vs_parsed_formula_match": detail["reported_vs_parsed_fractional_formula_match_0p03"],
            })
    if counters["OFFICIAL_PUBLIC_TEST_RESERVED_UNREAD"] != provenance["official_test_count"]:
        raise ValueError("official TEST physical embargo lost")
    if counters["ORIGINAL_PUBLIC_TRAIN"] != provenance["official_train_count"]:
        raise ValueError("original TRAIN admission not exhaustive")
    linked = counters["TRAIN_CIF_MATCH"] + counters["TRAIN_CIF_CLOSE_MATCH"]
    if (linked + counters["TRAIN_CIF_NO_MATCH"] != counters["ORIGINAL_PUBLIC_TRAIN"]
        or sum(value for key,value in counters.items() if key.startswith("PARSE_")) != linked):
        raise ValueError("original TRAIN CIF and parse populations do not reconcile")
    # deterministic, fixed priority: identify partial occupancy for *paper review*
    # before model-ready ordered crystals; never claim completed paper review.
    rows.sort(key=lambda item: (
        0 if item["fractional_site_count"] > 0 else 1,
        0 if item["reported_vs_parsed_formula_match"] else 1,
        item["source_entry_id"],
    ))
    queue = [{**r, "paper_review_status": "NOT_REVIEWED",
              "phase_identity": "UNATTESTED",
              "measurement_temperature_kelvin": None,
              "conductivity_bulk_vs_total": "UNVERIFIED",
              "experimental_sample_identity": "UNVERIFIED"}
             for r in rows[:MAX_REVIEW]]
    screen, _ = inspect_original_train_cifs(
        source, expected_commit=expected_commit,
        require_official=require_official,
    )
    report = {
        "schema_version": SCHEMA,
        "scope": "OFFICIAL_OBELIX_TRAIN_SOURCE_CIF_AUDIT" if require_official
                 else "SYNTHETIC_ORIGINAL_SOURCE_STRUCTURE_FIXTURE",
        "original_commit": provenance["source_commit"],
        "original_processed_csv_sha256": provenance["processed_csv_sha256"],
        "source_CIF_inventory_sha256": provenance["cif_inventory_sha256"],
        "original_all_source_rows": provenance["record_count"],
        "original_official_train_rows": counters["ORIGINAL_PUBLIC_TRAIN"],
        "original_official_test_rows_reserved_unparsed": counters["OFFICIAL_PUBLIC_TEST_RESERVED_UNREAD"],
        "all_original_source_linked_CIFs_including_reserved_TEST": provenance["available_cif_count"],
        "train_exact_match_source_CIF_count": counters["TRAIN_CIF_MATCH"],
        "train_close_match_CIF_count_NOT_phase_qualified": counters["TRAIN_CIF_CLOSE_MATCH"],
        "train_no_matched_CIF_count": counters["TRAIN_CIF_NO_MATCH"],
        "train_CIF_parse_category_counts": dict(sorted((k[6:],v) for k,v in counters.items() if k.startswith("PARSE_"))),
        "train_link_type_by_parse_status": dict(sorted(combinations.items())),
        "train_parsed_structures_with_site_diagnostics": counters["PARSED_STRUCTURES"],
        "train_structures_containing_fractional_occupancy_sites": counters["STRUCTURES_WITH_FRACTIONAL_SITES"],
        "train_structures_containing_partial_vacancy_sites": counters["STRUCTURES_WITH_VACANCY_SITES"],
        "train_structures_containing_mixed_species_sites": counters["STRUCTURES_WITH_MIXED_SPECIES_SITES"],
        "train_site_count_total_fractional": counters["FRACTIONAL_SITE_TOTAL"],
        "train_parsed_structure_reported_composition_mismatch_count": counters["PUBLISHER_REPORTED_PARSED_COMPOSITION_MISMATCH_0P03"],
        "reproduced_0145_train_model_eligible_ORDERED_source_structures": screen["eligible_distinct_train_source_records_NOT_independent_materials"],
        "reproduced_0145_structure_screen_status": screen["train_geometry_eligibility_counts"],
        "review_queue_first_party_public_DOI_and_source_CIF_links_ONLY": queue,
        "source_paper_review_queue_count": len(queue),
        "primary_source_papers_actually_read": 0,
        "specimen_phase_and_exact_measurement_temperature_verified": 0,
        "new_independent_physical_materials_qualified": 0,
        "geometry_CIF_close_match_promoted_to_exact_phase": False,
        "partial_occupancy_rounded_into_ordered_model": False,
        "MD_or_ionic_transport_computed_this_checkpoint": False,
        "scientific_qualification_authorized": False,
        "P0_01_status": "BLOCKED",
        "P0_02_status": "BLOCKED",
        "P0_03_status": "BLOCKED",
    }
    if require_official and report["reproduced_0145_train_model_eligible_ORDERED_source_structures"] != 39:
        raise ValueError("real original ordered-only MACE source count changed")
    return report


def run_original_cif_audit(checkout: Path, out: Path, *, expected_commit=SOURCE_COMMIT,
                           require_official=True):
    root=Path(checkout).resolve(strict=True)
    dest=Path(out).resolve()
    if dest.exists() or dest == root or root in dest.parents:
        raise ValueError("new audit output must not modify publisher original source")
    report=analyze_pinned_train_cif_cohort(
        root,expected_commit=expected_commit,require_official=require_official)
    dest.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".rhombus-0151-",dir=dest.parent))
    try:
        (stage/"cif_occupancy_source_audit_aggregate.json").write_bytes(
            _json_bytes(report)+b"\n")
        if dest.exists():
            raise ValueError("audit output already claimed")
        stage.rename(dest)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args(argv)
    try:
        report=run_original_cif_audit(a.original_obelix_checkout,a.output_dir)
    except (OSError,ValueError,TypeError) as exc:
        p.error(str(exc))
    print(json.dumps({
        "train_rows":report["original_official_train_rows"],
        "reserved_test":report["original_official_test_rows_reserved_unparsed"],
        "train_match":report["train_exact_match_source_CIF_count"],
        "train_close_match":report["train_close_match_CIF_count_NOT_phase_qualified"],
        "train_with_fractional_sites":report["train_structures_containing_fractional_occupancy_sites"],
        "MACE_ordered_source_eligible":report["reproduced_0145_train_model_eligible_ORDERED_source_structures"],
        "paper_review_queued":report["source_paper_review_queue_count"],
        "paper_review_verified":0,
        "scientific_go":False,
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
