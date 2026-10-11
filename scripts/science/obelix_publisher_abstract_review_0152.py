"""0152-B: original OBELiX 10-CIF queue x 8 first-party publication abstracts.

Source queue is RECOMPUTED on the pinned upstream TRAIN CIF corpus and its
0151 original GitHub Actions artifact SHA256 is matched byte-for-byte.
Publisher abstract context is manually reviewed metadata, *not* full text,
source-row phase evidence, or authenticated numerical conductivity truth.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urlparse

from rhombus.qualification.obelix_benchmark_intake import (
    SOURCE_COMMIT, _json_bytes,
)
from scripts.science.obelix_original_cif_occupancy_0151 import (
    analyze_pinned_train_cif_cohort,
)

SCHEMA = "rhombus-0152-original-obelix-publisher-abstract-review-v1"
EVIDENCE_SCHEMA = "rhombus-0152-original-source-publisher-abstract-evidence-v1"
SOURCE_AUDIT_SHA256 = "960cf078fcac71b244a087f0e73d781614aa515d38e6964dcfffcd654f90070a"
ORIGINAL_REVIEWED_ROWS = 10
ORIGINAL_DISTINCT_DOIS = 8
EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] /
    "data/development/phase3_original_paper_abstract_review_0152_v1.json"
)
DOI_RE = re.compile(r"^10\.[0-9]{4,9}/[A-Za-z0-9._;()/:-]{1,128}$")
APPROVED_PUBLISHER_HOSTS = {"pubs.acs.org", "pubs.rsc.org"}


def _validated_record(metadata):
    if not isinstance(metadata, dict):
        raise ValueError("invalid curated first-party publisher abstract")
    doi = metadata.get("doi")
    if not isinstance(doi, str) or not DOI_RE.fullmatch(doi):
        raise ValueError("unverified source publisher DOI")
    url = metadata.get("publisher_url")
    if not isinstance(url, str) or len(url) > 320:
        raise ValueError("unverified original article URL")
    parsed = urlparse(url)
    # ACS DOI URLs embed the full DOI; RSC content/articlehtml URLs store
    # just its suffix. Both are publisher-authentic but distinct URL layouts.
    acs_path = (
        parsed.hostname == "pubs.acs.org"
        and doi.startswith("10.1021/")
        and parsed.path.casefold() == "/doi/" + doi.casefold()
    )
    rsc_path = (
        parsed.hostname == "pubs.rsc.org"
        and doi.startswith("10.1039/")
        and parsed.path.casefold() ==
        "/en/content/articlehtml/2018/ta/" + doi.split("/", 1)[1].casefold()
    )
    if (
        parsed.scheme != "https"
        or parsed.hostname not in APPROVED_PUBLISHER_HOSTS
        or parsed.username or parsed.password
        or parsed.query or parsed.fragment
        or not (acs_path or rsc_path)
    ):
        raise ValueError("publication URL does not bind exact original DOI")
    title = metadata.get("title")
    if not isinstance(title, str) or not 10 <= len(title) <= 380:
        raise ValueError("invalid primary publication title")
    family = metadata.get("published_material_series")
    if not isinstance(family, str) or not 2 <= len(family) <= 250:
        raise ValueError("invalid published composition series")
    methods = metadata.get("abstract_methods")
    risks = metadata.get("literature_risks")
    if (not isinstance(methods, list) or not 1 <= len(methods) <= 10
        or not isinstance(risks, list) or not 1 <= len(risks) <= 10
        or len(set(methods)) != len(methods)
        or len(set(risks)) != len(risks)
        or any(not isinstance(x, str) or not re.fullmatch(r"[A-Z0-9_]{3,90}", x)
               for x in methods + risks)):
        raise ValueError("invalid publisher abstract methods / scope risks")
    bounds = metadata.get("abstract_observed_structural_temperature_range_kelvin")
    if bounds is not None:
        if not (isinstance(bounds, list) and len(bounds) == 2 and
                all(isinstance(x, int) and 0 < x < 5000 for x in bounds) and
                bounds[0] <= bounds[1]):
            raise ValueError("invalid paper-level structural temperature annotation")
    if not isinstance(metadata.get("abstract_identifies_one_room_temperature_bulk_sample"), bool):
        raise ValueError("missing publisher abstract source temperature-scope field")
    return metadata


def review_exact_original_publisher_abstracts(audit, evidence, *, enforce_real_source=True):
    """Do not claim that an abstract proves a particular CIF or measured sample."""
    if not isinstance(audit, dict) or not isinstance(evidence, dict):
        raise ValueError("source audit and publication review must be typed objects")
    if (audit.get("scientific_qualification_authorized") is not False
        or audit.get("partial_occupancy_rounded_into_ordered_model") is not False
        or audit.get("geometry_CIF_close_match_promoted_to_exact_phase") is not False
        or audit.get("primary_source_papers_actually_read") != 0
        or audit.get("original_official_test_rows_reserved_unparsed", 0) < 1
        or audit.get("specimen_phase_and_exact_measurement_temperature_verified") != 0):
        raise ValueError("invalid previously frozen 0151 scientific source stop line")
    if evidence.get("schema_version") != EVIDENCE_SCHEMA or (
        evidence.get("evidence_method")
        != "MANUAL_REVIEW_OF_PUBLISHER_PUBLIC_INDEXED_TITLE_AND_ABSTRACT_NOT_FULL_PAPER"
    ):
        raise ValueError("missing publication abstract-only provenance")
    original_queue = audit.get("review_queue_first_party_public_DOI_and_source_CIF_links_ONLY")
    papers = evidence.get("publisher_abstracts")
    if not isinstance(original_queue, list) or not isinstance(papers, list):
        raise ValueError("invalid actual publisher source review joins")
    doi_map = {}
    for p in papers:
        rec = _validated_record(p)
        doi = rec["doi"].casefold()
        if doi in doi_map:
            raise ValueError("duplicate DOI falsely inflates published paper count")
        doi_map[doi] = rec
    if enforce_real_source and (
        audit.get("original_all_source_rows") != 599
        or audit.get("original_official_train_rows") != 478
        or audit.get("original_official_test_rows_reserved_unparsed") != 121
        or audit.get("reproduced_0145_train_model_eligible_ORDERED_source_structures") != 39
        or evidence.get("original_source_commit") != SOURCE_COMMIT
        or evidence.get("recomputed_0151_original_source_aggregate_sha256") != SOURCE_AUDIT_SHA256
        or len(original_queue) != ORIGINAL_REVIEWED_ROWS
        or len(doi_map) != ORIGINAL_DISTINCT_DOIS
    ):
        raise ValueError("real first-party original source 0151 artifact cohort has drifted")
    if evidence.get("interpretation_contract", {}).get("full_primary_papers_actually_read_count") != 0:
        raise ValueError("publisher abstract was falsely treated as read full publication")
    if evidence.get("interpretation_contract", {}).get("physical_independent_specimens_verified_count") != 0:
        raise ValueError("publisher abstracts were falsely promoted to physical sample truth")

    rows = []
    observed_doicounts = Counter()
    seen_ids = set()
    methods_count = Counter()
    literature_flags_count = Counter()
    for row in original_queue:
        if (not isinstance(row, dict) or row.get("original_cif_match") != "Match"
            or row.get("paper_review_status") != "NOT_REVIEWED"
            or row.get("phase_identity") != "UNATTESTED"):
            raise ValueError("source Phase or full-paper status has been falsely promoted")
        sid = row.get("source_entry_id")
        if not isinstance(sid, str) or not sid or sid in seen_ids:
            raise ValueError("duplicate or invalid original source TRAIN CIF")
        seen_ids.add(sid)
        digest = row.get("original_cif_sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("original source linked CIF SHA256 missing")
        original_dois = row.get("source_dois")
        if not isinstance(original_dois, list) or len(original_dois) != 1:
            # Multiple DOIs need independent adjudication, never silently pick one.
            raise ValueError("ambiguous source evidence DOI association")
        doi = original_dois[0].casefold()
        if doi not in doi_map:
            raise ValueError("original source CIF DOI lacks inspected publisher abstract")
        inspected = doi_map[doi]
        observed_doicounts[doi] += 1
        for method in inspected["abstract_methods"]:
            methods_count[method] += 1
        for risk in inspected["literature_risks"]:
            literature_flags_count[risk] += 1
        rows.append({
            "source_entry_id": sid,
            "original_linked_CIF_sha256": digest,
            "original_publisher_DOI": doi,
            "publisher_abstract_url": inspected["publisher_url"],
            "publisher_abstract_title_reviewed": True,
            "publisher_abstract_review_scope": "PUBLIC_PUBLISHER_INDEXED_ABSTRACT_ONLY",
            "published_composition_series_context_only": inspected["published_material_series"],
            "paper_level_methods_context_only": list(inspected["abstract_methods"]),
            "paper_level_risks_context_only": list(inspected["literature_risks"]),
            "site_fractional_occupancy_in_original_CIF": row["fractional_site_count"] > 0,
            "paper_series_to_exact_CIF_composition_and_phase_match": "UNVERIFIED",
            "independent_paper_full_text_and_SI_review": "NOT_DONE",
            "row_specific_published_temperature": None,
            "row_specific_reported_numeric_conductivity": None,
            "row_specific_bulk_vs_total": "UNVERIFIED",
            "original_independent_experimental_specimen": "UNVERIFIED",
            "model_MD_transport_qualified": False,
        })
    if set(observed_doicounts) != set(doi_map) or len(rows) != len(original_queue):
        raise ValueError("unreferenced publisher paper or missing original source row")
    if enforce_real_source and (
        sorted(observed_doicounts.values()) != [1, 1, 1, 1, 1, 1, 2, 2]
    ):
        raise ValueError("ten original source CIFs did not bind eight actual DOI papers")

    audit_hash = hashlib.sha256(_json_bytes(audit) + b"\n").hexdigest()
    if enforce_real_source and audit_hash != SOURCE_AUDIT_SHA256:
        raise ValueError("0151 actual original Actions source artifact hash does not match")
    return {
        "schema_version": SCHEMA,
        "evidence_scope": "ACTUAL_ORIGINAL_TRAIN_CIF_TO_REVIEWED_PUBLISHER_PUBLIC_ABSTRACTS",
        "original_source_commit": audit["original_commit"],
        "original_processed_CSV_sha256": audit["original_processed_csv_sha256"],
        "original_CIF_inventory_sha256": audit["source_CIF_inventory_sha256"],
        "0151_real_source_audit_json_sha256": audit_hash,
        "official_original_public_TRAIN_rows": audit["original_official_train_rows"],
        "official_original_public_TEST_rows_reserved_unparsed": audit["original_official_test_rows_reserved_unparsed"],
        "original_exact_matched_CIFs": audit["train_exact_match_source_CIF_count"],
        "original_close_match_CIFs_not_phase_qualified": audit["train_close_match_CIF_count_NOT_phase_qualified"],
        "source_CIF_review_queue_rows_linked_to_paper_abstract": len(rows),
        "unique_publisher_DOIs_whose_indexed_abstracts_actually_inspected": len(observed_doicounts),
        "actual_DOI_paper_to_original_CIF_source_row_counts": dict(sorted(observed_doicounts.items())),
        "source_paper_abstract_experimental_method_occurrences_across_rows": dict(sorted(methods_count.items())),
        "source_paper_abstract_literature_scope_flags_across_rows": dict(sorted(literature_flags_count.items())),
        "first_party_original_source_CIF_abstract_review_entries": rows,
        "full_primary_source_papers_actually_read": 0,
        "original_publisher_supplementary_tables_directly_inspected": 0,
        "specific_experimental_sample_to_CIF_phase_independently_matched": 0,
        "specific_measured_temperature_bulk_total_to_source_row_matched": 0,
        "new_independently_qualified_experimental_materials": 0,
        "independent_physical_specimen_count_verified": None,
        "partial_occupancy_resolved_for_MACE": False,
        "MD_or_ionic_transport_computed_here": False,
        "scientific_GO": False,
        "P0_01_status": "BLOCKED",
        "P0_02_status": "BLOCKED",
        "P0_03_status": "BLOCKED",
    }


def run_actual_original_source_paper_abstract_review(checkout: Path, out: Path,
                                                      evidence_path: Path = EVIDENCE_PATH):
    original = Path(checkout).resolve(strict=True)
    dest = Path(out).resolve()
    if dest.exists() or dest == original or original in dest.parents:
        raise ValueError("original source must not be modified by paper review")
    evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    source_audit = analyze_pinned_train_cif_cohort(original)
    joined = review_exact_original_publisher_abstracts(source_audit, evidence)
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".obelix-0152-review-", dir=dest.parent))
    try:
        (staging / "source_publisher_abstract_review_aggregate.json").write_bytes(
            _json_bytes(joined) + b"\n")
        if dest.exists():
            raise ValueError("source abstract review output already claimed")
        staging.rename(dest)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return joined


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-obelix-checkout", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = run_actual_original_source_paper_abstract_review(
            args.original_obelix_checkout, args.output_dir)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        p.error(str(exc))
    print(json.dumps({
        "source_CIF_rows_joined": result["source_CIF_review_queue_rows_linked_to_paper_abstract"],
        "unique_first_party_abstract_DOIs": result["unique_publisher_DOIs_whose_indexed_abstracts_actually_inspected"],
        "full_papers_read": result["full_primary_source_papers_actually_read"],
        "individual_sample_phase_temp_conductivity_verified": 0,
        "scientific_GO": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
