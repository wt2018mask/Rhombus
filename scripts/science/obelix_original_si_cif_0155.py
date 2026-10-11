"""0155-B: publisher original CIF versus pinned OBELiX TRAIN geometry diagnostic.

A 8x2 crystal comparison cannot certify the phase of a measured specimen,
measurement temperature, bulk/total conductivity or independent validation.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, build_opener
import zipfile
from rhombus.qualification.obelix_benchmark_intake import (
    SOURCE_COMMIT, _json_bytes, build_obelix_benchmark_intake,
)
from scripts.science.obelix_original_cif_occupancy_0151 import (
    _source_verified_cif, analyze_pinned_train_cif_cohort,
)
from scripts.science.obelix_publisher_abstract_review_0152 import SOURCE_AUDIT_SHA256
from scripts.science.obelix_figshare_source_0154 import (
    _bounded_json, API_SEARCH, API_DETAIL, MAX_RESULTS,
    EXPECTED_VERIFIED_SHA256, qualified_detail,
)
from scripts.science.obelix_supplementary_source_0154 import (
    MAX_BYTES, PAPER_DOI, checked_url, ScopedRedirects, check_cif_archive,
)

EXPECTED_SI_CIF = 8
EXPECTED_TRAIN_ROWS = 2
MAX_STRUCT_SITES = 1500


def download_pinned_publisher_zip() -> bytes:
    found = _bounded_json(API_SEARCH, {
        "search_for": "Correlating Transport and Structural Properties",
        "resource_doi": PAPER_DOI, "page": 1, "page_size": MAX_RESULTS,
    })
    if not isinstance(found, list) or len(found) > MAX_RESULTS:
        raise ValueError("unbounded original Figshare metadata")
    eligible = {}
    for item in found:
        if not isinstance(item, dict) or type(item.get("id")) is not int:
            continue
        detail = _bounded_json(API_DETAIL + str(item["id"]))
        if not isinstance(detail, dict) or str(detail.get("resource_doi") or "").casefold() != PAPER_DOI.casefold():
            continue
        for f in qualified_detail(detail):
            if f["role"] == "experimental_cif_zip":
                eligible[(f["url"], f["size"])] = f
    if len(eligible) != 1:
        raise ValueError("original publisher DOI does not identify one unique ZIP")
    f = next(iter(eligible.values()))
    if not checked_url(f["url"]):
        raise ValueError("untrusted original source URL")
    opener = build_opener(ScopedRedirects())
    with opener.open(Request(f["url"], headers={"Accept":"application/octet-stream"}), timeout=35) as response:
        if not checked_url(response.geturl()):
            raise ValueError("Figshare redirect escaped exact host allowlist")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) != f["size"]:
        raise ValueError("published Figshare file size drift")
    audit = check_cif_archive(raw)
    if (audit["source_bytes_sha256"] != EXPECTED_VERIFIED_SHA256["experimental_cif_zip"]
        or audit["cif_member_count"] != EXPECTED_SI_CIF):
        raise ValueError("pinned actual publisher primary CIF source changed")
    return raw


def describe_cif(raw: bytes):
    digest = hashlib.sha256(raw).hexdigest()
    try:
        from pymatgen.core import Structure
        structure = Structure.from_str(raw.decode("utf-8-sig"), fmt="cif")
        if not 1 <= len(structure) <= MAX_STRUCT_SITES:
            raise ValueError("unsupported source atomic sites")
        fractional = vacancies = mixed = 0
        for site in structure:
            parts = [float(v) for v in site.species.values()]
            if any(not 0 <= v <= 1.000001 for v in parts) or sum(parts) > 1.000001:
                raise ValueError("invalid source site occupancy")
            fractional += int(any(abs(v-1.0) > 1e-6 for v in parts))
            vacancies += int(sum(parts) < 1-1e-6)
            mixed += int(len(parts) > 1)
        return structure, {
            "cif_sha256": digest, "parse_state": "PARSED",
            "reduced_formula": structure.composition.reduced_formula,
            "sites": len(structure), "fractional_sites": fractional,
            "vacancy_sites": vacancies, "mixed_sites": mixed,
            "occupancies_preserved_no_ordering": True,
        }
    except (ValueError, UnicodeError, TypeError, KeyError, IndexError, OverflowError) as exc:
        return None, {"cif_sha256": digest, "parse_state": "REJECTED",
                      "reason_type": type(exc).__name__,
                      "occupancies_preserved_no_ordering": True}


def compare_geometry(a, b):
    result = {"atomic_fraction_max_abs_gap": None,
              "composition_compatible_0p02_diagnostic": False,
              "geometry_equivalent_heuristic": None,
              "measured_sample_or_phase_match": "UNVERIFIED"}
    if a is None or b is None:
        return result
    ca = a.composition.fractional_composition.get_el_amt_dict()
    cb = b.composition.fractional_composition.get_el_amt_dict()
    gap = max(abs(float(ca.get(e, 0))-float(cb.get(e, 0))) for e in (set(ca)|set(cb)))
    result["atomic_fraction_max_abs_gap"] = round(gap, 8)
    result["composition_compatible_0p02_diagnostic"] = bool(gap <= 0.02)
    if gap <= 0.02:
        try:
            from pymatgen.analysis.structure_matcher import StructureMatcher
            result["geometry_equivalent_heuristic"] = bool(
                StructureMatcher(ltol=0.2, stol=0.3, angle_tol=5,
                                 primitive_cell=False, scale=True).fit(a,b))
        except (ValueError, TypeError, ArithmeticError, RuntimeError, IndexError):
            result["geometry_equivalent_heuristic"] = None
    return result


def compare_actual_sources(checkout: Path, zip_data: bytes, official=True):
    checkout = Path(checkout).resolve(strict=True)
    audit = analyze_pinned_train_cif_cohort(
        checkout, expected_commit=SOURCE_COMMIT, require_official=official)
    digest = hashlib.sha256(_json_bytes(audit)+b"\n").hexdigest()
    if official and (digest != SOURCE_AUDIT_SHA256 or
        audit["original_official_train_rows"] != 478 or
        audit["original_official_test_rows_reserved_unparsed"] != 121):
        raise ValueError("frozen 0151 original TRAIN source audit changed")
    targets = [q for q in audit["review_queue_first_party_public_DOI_and_source_CIF_links_ONLY"]
               if q.get("source_dois") == [PAPER_DOI] and q.get("original_cif_match") == "Match"]
    if official and len(targets) != EXPECTED_TRAIN_ROWS:
        raise ValueError("original two publisher DOI source-linked TRAIN CIF entries changed")
    rows, provenance = build_obelix_benchmark_intake(checkout, expected_commit=SOURCE_COMMIT)
    ids = {q["source_entry_id"] for q in targets}
    by_id = {}
    for row in rows:
        if row["official_split"] != "TRAIN":
            continue
        if row["source_entry_id"] in ids:
            if row["source_entry_id"] in by_id:
                raise ValueError("duplicate source TRAIN entry ID")
            by_id[row["source_entry_id"]] = row
    if len(by_id) != len(ids):
        raise ValueError("missing pinned original TRAIN source row")
    source = []
    for item in targets:
        row = by_id[item["source_entry_id"]]
        if (row["reference_dois"] != [PAPER_DOI] or
            row["cif_content_sha256"] != item["original_cif_sha256"]):
            raise ValueError("original paper DOI or CIF hash association shifted")
        obj, info = describe_cif(_source_verified_cif(checkout,row))
        source.append((obj, dict(info,source_entry_id=item["source_entry_id"])))
    inventory = check_cif_archive(zip_data)
    if official and (inventory["source_bytes_sha256"] !=
        EXPECTED_VERIFIED_SHA256["experimental_cif_zip"] or
        inventory["cif_member_count"] != EXPECTED_SI_CIF):
        raise ValueError("source verified original publisher CIF ZIP mismatch")
    si = []
    with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
        for member in z.infolist():
            if member.filename.casefold().endswith(".cif"):
                si.append(describe_cif(z.read(member)))
    if official and len(si) != EXPECTED_SI_CIF:
        raise ValueError("published SI structures have drifted")
    pairs = [
        {"source_train_entry_id": original[1]["source_entry_id"],
         "source_cif_sha256": original[1]["cif_sha256"],
         "publisher_cif_sha256": publisher[1]["cif_sha256"],
         **compare_geometry(original[0],publisher[0])}
        for original in source for publisher in si
    ]
    return {
        "schema_version": "rhombus-0155-real-publisher-original-cif-v-train-diagnostic-v1",
        "original_OBELiX_commit": provenance["source_commit"],
        "original_0151_audit_sha256": digest,
        "source_DOI": PAPER_DOI,
        "publisher_SI_ZIP_sha256": inventory["source_bytes_sha256"],
        "original_public_TRAIN_rows": audit["original_official_train_rows"],
        "original_public_TEST_rows_reserved_unread": audit["original_official_test_rows_reserved_unparsed"],
        "exact_match_original_TRAIN_rows_reexamined": len(source),
        "publisher_original_SI_CIF_members_reexamined": len(si),
        "structure_pair_attempts": len(pairs),
        "source_records": [d for _,d in source],
        "publisher_CIF_records": [d for _,d in si],
        "pair_diagnostics": pairs,
        "composition_compatible_pairs_diagnostic_only": sum(p["composition_compatible_0p02_diagnostic"] for p in pairs),
        "geometry_equivalent_pairs_diagnostic_only": sum(p["geometry_equivalent_heuristic"] is True for p in pairs),
        "source_row_sample_x_and_experimental_phase_qualified": 0,
        "source_row_temperature_bulk_total_conductivity_qualified": 0,
        "independent_experimental_specimens_verified": 0,
        "disorder_rounded_or_model_qualified": False,
        "MD_transport_computed": False, "scientific_GO": False,
        "P0_01_status":"BLOCKED","P0_02_status":"BLOCKED","P0_03_status":"BLOCKED",
        "next":"0156-B verify paper sample x, phase, occupancy, measurement temperature and bulk/total with publisher original tables",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--original-obelix-checkout", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--live-original", action="store_true")
    args = p.parse_args()
    if not args.live_original or args.output_dir.exists():
        p.error("require explicit real publisher source opt-in and new output directory")
    source_zip = download_pinned_publisher_zip()
    result = compare_actual_sources(args.original_obelix_checkout, source_zip)
    args.output_dir.mkdir(parents=True)
    (args.output_dir/"original_primary_CIF_crosscheck.json").write_text(
        json.dumps(result, indent=2, sort_keys=True)+"\n")
    print("0155_REAL_PRIMARY_PUBLISHER_CIF_V_ORIGINAL_TRAIN_STRUCTURE_AUDIT")
    print(json.dumps({
        "original_TRAIN_CIF":result["exact_match_original_TRAIN_rows_reexamined"],
        "publisher_CIF":result["publisher_original_SI_CIF_members_reexamined"],
        "attempted_pairs":result["structure_pair_attempts"],
        "composition_compatible":result["composition_compatible_pairs_diagnostic_only"],
        "geometry_heuristic_fits":result["geometry_equivalent_pairs_diagnostic_only"],
        "verified_independent_specimens":0,"scientific_GO":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
