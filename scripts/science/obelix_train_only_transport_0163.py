"""0163-B: strict TRAIN-only original OBELiX physics targets.

Different from the legacy general catalog, this scanner never CSV-decodes
or parses any TEST composition/DOI/conductivity field. Its original
processed.csv is a MIXED file, so the whole stream necessarily passes over
TEST *raw bytes*: do not claim inaccessible source bytes. Only official
TEST ID split membership and first-column ASCII IDs are inspected.

Original source pin and selected TRAIN-only original CIF/DOI provenance are
checked directly. Never call legacy build_obelix_benchmark_intake,
0155 compare_actual_sources or any helper that builds a full mixed catalog.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import tempfile

from rhombus.qualification.obelix_benchmark_intake import (
    SOURCE_COMMIT, CONDUCTIVITY_COLUMN, REQUIRED_COLUMNS,
    MAX_CSV_BYTES, MAX_SPLIT_BYTES, _official_split, _read_bounded, _conductivity,
    _json_bytes,
)
from rudeus.generation.candidate_supply_obelix_adapter import _git_identity
from scripts.science.obelix_lagp_nominal_series_0156 import (
    MATCHES, MANUSCRIPT_SHA, nominal_x, refined_x, indexed_publisher_cifs,
    fetch_with_bounded_transient_retries, _fetch_original_pdf, publisher_pdf_bytes,
)
from scripts.science.obelix_original_si_cif_0155 import (
    download_pinned_publisher_zip, describe_cif, compare_geometry,
)
from scripts.science.obelix_lagp_measurement_target_0162 import (
    paper_transport_method_audit,
)
from scripts.science.obelix_public_manuscript_0153 import audit_manuscript
from scripts.science.obelix_figshare_source_0154 import EXPECTED_VERIFIED_SHA256
from scripts.science.obelix_supplementary_source_0154 import PAPER_DOI

SCHEMA="rhombus-0163-strict-TRAIN-only-original-LAGP-physical-target-v1"
OFFICIAL_TRAIN=478
RESERVED_TEST=121
ORIGINAL_ALL=599
TARGETS=frozenset(MATCHES)
MAX_PHYSICAL_LINE=32768
MAX_STABLE_ID=128
ID_RE=re.compile(rb"[A-Za-z0-9_-]{1,128}")


def _row_id_prefix(physical:bytes)->str:
    """Read only the unquoted ASCII first-column ID; never parse other fields."""
    prefix,delimiter,_=physical.partition(b",")
    if not delimiter or not ID_RE.fullmatch(prefix) or len(prefix)>MAX_STABLE_ID:
        raise ValueError("missing/unquoted original source physical-line ID")
    return prefix.decode("ascii")


def scan_pinned_train_only(root:Path, *, official=True)->dict:
    root=Path(root).resolve(strict=True)
    head,_tree=_git_identity(root)
    if official and head!=SOURCE_COMMIT:
        raise ValueError("original upstream source checkout pinned SHA drift")
    train_path=root/"data/train_idx.csv"
    test_path=root/"data/test_idx.csv"
    train=set(_official_split(_read_bounded(train_path,MAX_SPLIT_BYTES),name="train"))
    test=set(_official_split(_read_bounded(test_path,MAX_SPLIT_BYTES),name="test"))
    if train & test or not train or not test:
        raise ValueError("overlapping, empty or invalid upstream official split IDs")
    if official and (len(train),len(test))!=(OFFICIAL_TRAIN,RESERVED_TEST):
        raise ValueError("official TRAIN/TEST identifier census drift")
    stream=root/"data/processed.csv"
    if stream.is_symlink() or not stream.is_file():
        raise ValueError("source processed csv missing or unsafe")
    digest=hashlib.sha256()
    rows={}
    seen=set()
    counters=Counter()
    with stream.open("rb") as file:
        header=file.readline(MAX_PHYSICAL_LINE+1)
        if len(header)>MAX_PHYSICAL_LINE or not header:
            raise ValueError("original CSV header malformed/overlong")
        digest.update(header)
        columns=next(csv.reader([header.decode("utf-8-sig").rstrip("\r\n")]))
        if (not columns or columns[0]!="ID" or len(columns)!=len(set(columns))
            or any(k not in columns for k in REQUIRED_COLUMNS)):
            raise ValueError("source CSV header/required columns mismatch")
        size=len(header)
        for physical in file:
            digest.update(physical)
            size+=len(physical)
            if size>MAX_CSV_BYTES or len(physical)>MAX_PHYSICAL_LINE:
                raise ValueError("source mixed CSV bytes/physical line exceeded limit")
            identifier=_row_id_prefix(physical)
            if identifier in seen:
                raise ValueError("duplicate original source CSV identifier")
            seen.add(identifier)
            if identifier in test:
                counters["TEST_row_ids_only_no_other_fields_parsed"]+=1
                continue   # no UTF-8 decoding/csv.reader on TEST content
            if identifier not in train:
                raise ValueError("original CSV ID outside official TRAIN or TEST")
            decoded=physical.decode("utf-8")
            values=next(csv.reader([decoded.rstrip("\r\n")],strict=True))
            if len(values)!=len(columns) or values[0]!=identifier:
                raise ValueError("original TRAIN CSV row broken or multiline unsupported")
            row=dict(zip(columns,values))
            censored,value=_conductivity(row[CONDUCTIVITY_COLUMN])
            counters["TRAIN_total"]+=1
            counters["TRAIN_"+censored]+=1
            if identifier in TARGETS:
                dois=[x.strip().lower() for x in row["DOI"].split("|") if x.strip()]
                if dois!=[PAPER_DOI] or row["CIF"].strip()!="Match":
                    raise ValueError("frozen original LAGP target DOI/CIF declared linkage changed")
                rows[identifier]={
                    "source_entry_id":identifier,"official_split":"TRAIN",
                    "source_snapshot_commit":head,"reference_dois":dois,
                    "reported_ionic_conductivity_text":value,
                    "reported_ionic_conductivity_unit":"S/cm",
                    "measurement_kind":censored,
                    "reported_temperature_scope":"ROOM_TEMPERATURE_EXACT_K_UNSPECIFIED",
                    "source_cif_match_status":row["CIF"].strip(),
                    "source_label_is_independently_qualified":False,
                }
        if size>MAX_CSV_BYTES:
            raise ValueError("source CSV exceeds byte cap")
    if seen!=train|test:
        raise ValueError("processed CSV does not exactly cover official split ID union")
    if counters["TRAIN_total"]!=len(train) or counters["TEST_row_ids_only_no_other_fields_parsed"]!=len(test):
        raise ValueError("source TRAIN/TEST row count drift")
    if set(rows)!=TARGETS:
        raise ValueError("original LAGP two TRAIN rows missing")
    return {
        "pinned_git_commit":head,
        "processed_mixed_csv_SHA256":digest.hexdigest(),
        "official_TRAIN_ids":len(train),"official_TEST_ids":len(test),
        "source_TRAIN_parsed_rows":counters["TRAIN_total"],
        "source_TEST_only_first_column_IDs_seen":counters["TEST_row_ids_only_no_other_fields_parsed"],
        "source_TEST_DOI_formula_conductivity_cells_parsed":0,
        "source_TEST_CIF_bytes_read":0,
        "single_processed_CSV_stream_raw_TEST_bytes_passed_over":True,
        "source_reader_not_a_cryptographic_blind":True,
        "TRAIN_reported_numeric_point":counters["TRAIN_PROCESSED_REPORTED_POINT"],
        "TRAIN_censored_upper_bound":counters["TRAIN_UPPER_BOUND"],
        "processed_file_may_flatten_original_raw_censoring":True,
        "raw_workbook_original_449_point_29_censored_not_rechecked_in_this_pipeline":True,
        "_ephemeral_train_targets":rows,
    }


def _pinned_train_crystal(root:Path, source_id:str)->bytes:
    if source_id not in TARGETS:
        raise ValueError("only originally source-verified TRAIN LAGP target CIF IDs")
    path=root/"data/randomized_cifs"/(source_id+".cif")
    if path.is_symlink() or not path.is_file() or path.resolve(strict=True).parent!=(root/"data/randomized_cifs").resolve(strict=True):
        raise ValueError("original TRAIN CIF source path unsafe")
    with path.open("rb") as f:
        raw=f.read(16*1024*1024+1)
    if len(raw)>16*1024*1024 or hashlib.sha256(raw).hexdigest()!=MATCHES[source_id][0]:
        raise ValueError("frozen original TRAIN crystal content SHA drift")
    return raw


def strict_train_physical_targets(root:Path, *, official=True, fetch_external=True)->dict:
    checked=scan_pinned_train_only(root,official=official)
    targets=checked.pop("_ephemeral_train_targets")
    if official and (checked["TRAIN_reported_numeric_point"],checked["TRAIN_censored_upper_bound"])!=(478,0):
        raise ValueError("original processed CSV point-like metadata census drift; raw censor adjudication separate")
    rawzip=download_pinned_publisher_zip()
    index=indexed_publisher_cifs(rawzip)
    from zipfile import ZipFile
    cifs={}
    with ZipFile(io.BytesIO(rawzip)) as z:
        for item in z.infolist():
            if item.filename.lower().endswith(".cif"):
                raw=z.read(item)
                digest=hashlib.sha256(raw).hexdigest()
                if digest in MATCHES.values():
                    raise ValueError("unapproved publisher identity structure type")
                cifs[digest]=raw
    results=[]
    source_log={}
    for rid in sorted(TARGETS):
        src_sha,pub_sha=MATCHES[rid]
        if pub_sha not in index or pub_sha not in cifs:
            raise ValueError("missing exact original publisher CIF hash")
        nominal=nominal_x(index[pub_sha])
        if abs(nominal-({"0fh":0.2,"1dm":0.6}[rid]))>1e-8:
            raise ValueError("original nominal publisher sample label drift")
        train_raw=_pinned_train_crystal(root,rid)
        sample,source_detail=describe_cif(train_raw)
        original,publisher_detail=describe_cif(cifs[pub_sha])
        fit=compare_geometry(sample,original)
        if (source_detail["cif_sha256"]!=src_sha or
            publisher_detail["cif_sha256"]!=pub_sha or
            source_detail["parse_state"]!="PARSED" or
            publisher_detail["parse_state"]!="PARSED" or
            fit["geometry_equivalent_heuristic"] is not True or
            fit["composition_compatible_0p02_diagnostic"] is not True):
            raise ValueError("real original TRAIN structure-to-publisher fit drift")
        row=targets[rid]
        if row["measurement_kind"]!="PROCESSED_REPORTED_POINT" or row["source_label_is_independently_qualified"]:
            raise ValueError("source label is unadmitted or censored")
        try:
            val=Decimal(row["reported_ionic_conductivity_text"])
        except (InvalidOperation,TypeError) as err:
            raise ValueError("invalid original TRAIN numeric source truth") from err
        if not val.is_finite() or val<=0:
            raise ValueError("invalid original TRAIN positive conductivity")
        source_log[rid]=math.log10(float(val))
        results.append({
            "original_TRAIN_id":rid,"publisher_original_CIF_sha256":pub_sha,
            "source_original_CIF_sha256":src_sha,
            "original_publisher_filename":index[pub_sha],
            "publisher_nominal_Al_x":nominal,
            "publisher_refined_Al_x":refined_x(publisher_detail["reduced_formula"])["Al"],
            "original_structural_fit_heuristic_only":True,
            "original_cif_site_count":source_detail["sites"],
            "original_cif_fractional_sites":source_detail["fractional_sites"],
            "source_qualifies_as_same_pellet_phase_temperature_bulk_total":False,
            "ready_for_physical_MLIP_MD_as_experiment_reference":False,
        })
    manuscript=fetch_with_bounded_transient_retries(_fetch_original_pdf)
    if hashlib.sha256(manuscript).hexdigest()!=MANUSCRIPT_SHA or not audit_manuscript(manuscript)["document_text_DOI_match"]:
        raise ValueError("original accepted paper primary DOI/digest drift")
    si=fetch_with_bounded_transient_retries(publisher_pdf_bytes)
    if hashlib.sha256(si).hexdigest()!=EXPECTED_VERIFIED_SHA256["rietveld_si_pdf"]:
        raise ValueError("original Rietveld SI exact primary source digest drift")
    method=paper_transport_method_audit(manuscript)
    ratio=round(source_log["1dm"]-source_log["0fh"],8)
    return {
        "schema_version":SCHEMA,
        "source_paper_DOI":PAPER_DOI,
        "original_SOURCE_git_commit":checked["pinned_git_commit"],
        "original_processed_CSV_SHA256":checked["processed_mixed_csv_SHA256"],
        "source_TRAIN_intake_summary":{k:v for k,v in checked.items() if k not in ("pinned_git_commit","processed_mixed_csv_SHA256")},
        "original_TEST_label_formula_DOI_CIF_FIELDS_CSV_PARSED":0,
        "TEST_raw_line_bytes_present_in_mixed_csv_stream":True,
        "exact_source_CIF_publisher_hashes_verified":True,
        "original_publisher_CIF_archive_SHA256":hashlib.sha256(rawzip).hexdigest(),
        "real_author_original_manuscript_SHA256":hashlib.sha256(manuscript).hexdigest(),
        "real_rietveld_SI_SHA256":hashlib.sha256(si).hexdigest(),
        "original_TWO_source_TRAIN_structure_and_label_leads":results,
        "processed_source_TRAIN_label_log10_ratio_1dm_minus_0fh":ratio,
        "reproduces_0162_original_processed_label_ratio":ratio==0.76937121 if official else None,
        "real_primary_paper_transport_method_pages":method["transport_method_indicator_pages"],
        "paper_shows_reciprocal_resistance_instead_of_conductivity_context_only":bool(
            method["transport_method_indicator_pages"]["reciprocal_resistance"]
            and method["transport_method_indicator_pages"]["not_equivalent_to_conductivity"]),
        "paper_numeric_graph_sample_bulk_total_T_and_pellet_join_adjudicated":False,
        "processed_point_label_is_not_raw_measurement_point_admission":True,
        "actual_independently_qualified_transport_specimens":0,
        "new_external_blind":False,"new_finite_T_MD":False,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED","scientific_GO":False,
    }


def run_original(root:Path, out:Path)->dict:
    out=Path(out).resolve()
    checkout=Path(root).resolve(strict=True)
    if out.exists() or checkout==out or checkout in out.parents:
        raise ValueError("fresh aggregate location outside source checkout required")
    result=strict_train_physical_targets(checkout)
    out.parent.mkdir(parents=True,exist_ok=True)
    staged=Path(tempfile.mkdtemp(prefix=".rhombus-0163-",dir=out.parent))
    try:
        (staged/"strict_original_TRAIN_lagp_target_0163.json").write_bytes(_json_bytes(result)+b"\n")
        if out.exists():raise ValueError("source evidence output collision")
        staged.rename(out)
    finally:
        if staged.exists():shutil.rmtree(staged)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args()
    out=run_original(args.original_obelix_checkout,args.output_dir)
    print("0163_STRICT_TRAIN_ONLY_SOURCE_2_LAGP_TARGETS_AND_NO_TEST_CELLS_PARSED_PASS")
    print(json.dumps({
        "TRAIN":out["source_TRAIN_intake_summary"]["source_TRAIN_parsed_rows"],
        "TEST_cell_parses":out["original_TEST_label_formula_DOI_CIF_FIELDS_CSV_PARSED"],
        "train_ratio":out["processed_source_TRAIN_label_log10_ratio_1dm_minus_0fh"],
        "paper_method_reciprocal_R_context":out["paper_shows_reciprocal_resistance_instead_of_conductivity_context_only"],
        "qualified_physical_specimens":0,"science_GO":False},sort_keys=True))


if __name__=="__main__":main()
