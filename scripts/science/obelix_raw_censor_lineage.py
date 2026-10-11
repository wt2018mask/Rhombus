"""0133 inspect OBELiX's original raw.xlsx for lost censored measurements.

OBELiX's upstream preprocessing.py converts literal '<1E-10'/'<1E-8'
source values into numeric 1e-15 in processed.csv. This inspection is
source-bound, preserves the full original inequality, and NEVER treats the
numeric placeholder as an independently verified experimental point truth.

The public TEST source values remain held outside development worklists.
No dependency on openpyxl, network, GPU, model, or licensed paper downloads.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import subprocess
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

from rhombus.qualification.measurement_identity import _json_bytes
from scripts.science.obelix_adjudication_queue import build_adjudication_queue
from scripts.science.obelix_real_source_pipeline import SOURCE_COMMIT

SCHEMA = "rhombus-obelix-original-censor-audit-0133-v1"
MAX_XLSX_BYTES = 4 * 1024 * 1024
MAX_UNCOMPRESSED_XML = 8 * 1024 * 1024
MAX_WORKBOOK_ENTRIES = 80
MAX_WORKBOOK_ROWS = 2000
MAX_CELLS_PER_ROW = 100
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_COL = re.compile(r"^([A-Z]+)[1-9][0-9]*$")
_EXACT_UPPER = {"<1E-10", "<1E-8"}
_MAIN_COL = "Ionic conductivity (S cm-1)"


def _hash(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _decimal(text: str) -> Decimal | None:
    if not isinstance(text, str):
        return None
    try:
        n = Decimal(text.strip())
    except InvalidOperation:
        return None
    return n if n.is_finite() and n > 0 else None


def _xlsx_cells(blob: bytes) -> tuple[list[str], list[dict]]:
    """Read basic OOXML cells from frozen raw.xlsx, with ZIP and XML budgets."""
    if len(blob) > MAX_XLSX_BYTES:
        raise ValueError("original raw workbook exceeds source byte budget")
    try:
        with ZipFile(__import__("io").BytesIO(blob)) as z:
            members = z.infolist()
            if len(members) > MAX_WORKBOOK_ENTRIES:
                raise ValueError("original workbook ZIP has too many members")
            for meta in members:
                if meta.file_size > MAX_UNCOMPRESSED_XML:
                    raise ValueError("original workbook member exceeds XML budget")
                if ".." in meta.filename.split("/") or meta.filename.startswith("/"):
                    raise ValueError("unsafe workbook member path")
            names = set(z.namelist())
            if "xl/worksheets/sheet1.xml" not in names:
                raise ValueError("original workbook missing expected first worksheet")
            strings = []
            if "xl/sharedStrings.xml" in names:
                for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS):
                    strings.append("".join(t.text or "" for t in si.findall(".//m:t", _NS)))
                if len(strings) > 250000:
                    raise ValueError("too many original shared strings")
            root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    except (BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError("invalid original Excel XML/ZIP") from exc
    data = root.find("m:sheetData", _NS)
    if data is None:
        raise ValueError("original workbook has no sheetData")
    records: list[dict[int, str]] = []
    for sheet_row in data.findall("m:row", _NS):
        if len(records) >= MAX_WORKBOOK_ROWS:
            raise ValueError("original workbook exceeds row budget")
        cells: dict[int, str] = {}
        for cell in sheet_row.findall("m:c", _NS):
            if len(cells) >= MAX_CELLS_PER_ROW:
                raise ValueError("original workbook row exceeds cell budget")
            col_match = _COL.fullmatch(cell.get("r", ""))
            if col_match is None:
                raise ValueError("original workbook cell reference malformed")
            col = 0
            for c in col_match.group(1):
                col = col * 26 + (ord(c) - ord("A") + 1)
            col -= 1
            if col in cells:
                raise ValueError("duplicate original cell address")
            typ = cell.get("t")
            if typ == "inlineStr":
                value = "".join(x.text or "" for x in cell.findall(".//m:t", _NS))
            else:
                node = cell.find("m:v", _NS)
                raw = "" if node is None or node.text is None else node.text
                if typ == "s":
                    try:
                        value = strings[int(raw)]
                    except (ValueError, IndexError) as exc:
                        raise ValueError("invalid original shared-string reference") from exc
                elif typ in (None, "n", "str"):
                    value = raw
                else:
                    value = raw
            cells[col] = value.strip()
        records.append(cells)
    if not records:
        raise ValueError("empty original workbook")
    header_index = next((i for i, cells in enumerate(records[:12])
                         if "ID" in cells.values() and _MAIN_COL in cells.values()), None)
    if header_index is None:
        raise ValueError("expected raw ID and ionic conductivity headers missing")
    headers = {v: k for k, v in records[header_index].items() if v}
    if len(headers) != len([v for v in records[header_index].values() if v]):
        raise ValueError("duplicate original worksheet headers")
    wanted = ("ID", _MAIN_COL, "IC (Total)", "IC (Bulk)")
    if not all(key in headers for key in ("ID", _MAIN_COL)):
        raise ValueError("missing original measurement columns")
    out = []
    for cells in records[header_index + 1:]:
        rid = cells.get(headers["ID"], "")
        if not rid:
            continue
        if len(rid) > 80 or rid.strip() != rid:
            raise ValueError("bad original source entry ID")
        result = {key: cells.get(headers[key], "") if key in headers else ""
                  for key in wanted}
        if rid in {r["ID"] for r in out}:
            raise ValueError("duplicated original raw workbook ID")
        out.append(result)
    return list(headers), out


def build_original_censor_audit(
    checkout: Path, evidence_dir: Path, *, require_official: bool = True,
) -> tuple[list[dict], dict]:
    """Recover source inequality evidence and preserve public TEST exclusion."""
    source = Path(checkout).resolve(strict=True)
    if not source.is_dir():
        raise ValueError("original checkout must be a directory")
    try:
        pin = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(source), "status", "--porcelain", "--untracked-files=all"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError("unverified original Git checkout") from exc
    if dirty:
        raise ValueError("original raw source checkout must be clean")
    if require_official and pin != SOURCE_COMMIT:
        raise ValueError("raw workbook not from pinned official source")
    work, _, queue = build_adjudication_queue(
        evidence_dir, require_official=require_official,
    )
    if queue["upstream_source_commit"] != pin:
        raise ValueError("raw source commit differs from 0130-0131 source")
    path = source / "data" / "raw.xlsx"
    if path.is_symlink():
        raise ValueError("original raw source workbook is a symlink")
    with path.open("rb") as source_file:
        blob = source_file.read(MAX_XLSX_BYTES + 1)
    if len(blob) > MAX_XLSX_BYTES:
        raise ValueError("original raw source byte budget exceeded")
    raw_columns, raw_records = _xlsx_cells(blob)
    raw_by_id = {r["ID"]: r for r in raw_records}
    if len(raw_by_id) != len(raw_records):
        raise ValueError("duplicate original workbook IDs")
    # Independently inspect original source row records, without trusting
    # the developer/public-TEST-filtered 0131 worklist for source measurements.
    processed = [json.loads(line) for line in
                 (Path(evidence_dir) / "0127" / "records.jsonl").read_text().splitlines()]
    processed_ids = {r["source_entry_id"] for r in processed}
    if len(processed_ids) != len(processed):
        raise ValueError("duplicate processed source record ID")
    if processed_ids - set(raw_by_id):
        raise ValueError("processed source entry absent in raw workbook")
    by_work = {row["source_entry_id"]: row for row in work}
    if processed_ids != set(by_work):
        raise ValueError("raw census diverges from immutable 0131 worklist")
    output = []
    counts = Counter()
    censored_train = []
    for r in processed:
        rid = r["source_entry_id"]
        original = raw_by_id[rid]
        raw = original[_MAIN_COL].strip()
        processed_value = _decimal(r["reported_ionic_conductivity_text"])
        if processed_value is None:
            raise ValueError("processed source data not a positive numeric value")
        if raw.startswith("<"):
            if raw.upper().replace(" ", "") not in _EXACT_UPPER:
                raise ValueError("unexpected noncanonical raw upper-bound syntax")
            bound = _decimal(raw[1:])
            if bound is None:
                raise ValueError("malformed raw conductivity upper bound")
            if processed_value != Decimal("1e-15"):
                raise ValueError("source-censored value lacks expected numeric 1e-15 proxy")
            kind = "ORIGINAL_UPPER_BOUND_NUMERIC_PLACEHOLDER"
            counts["RAW_CENSORED"] += 1
        elif _decimal(raw) is not None:
            kind = "RAW_REPORTED_NUMERIC"
            counts["RAW_NUMERIC"] += 1
        else:
            kind = "RAW_NONNUMERIC_UNRESOLVED"
            counts["RAW_UNRESOLVED"] += 1
        split = r["official_split"]
        counts["ORIGINAL_" + split] += 1
        counts["CENSORED_" + split] += int(kind == "ORIGINAL_UPPER_BOUND_NUMERIC_PLACEHOLDER")
        if r["reported_ionic_conductivity_text"] == "1e-15":
            counts["PROCESSED_1E_MINUS_15"] += 1
        if split == "TEST":
            # No public TEST identifiers, raw values or component fields in
            # developer-facing review worklists. Aggregates only.
            continue
        if kind == "ORIGINAL_UPPER_BOUND_NUMERIC_PLACEHOLDER":
            censored_train.append(rid)
        output.append({
            "schema_version": SCHEMA,
            "source_entry_id": rid,
            "source_record_sha256": by_work[rid]["source_record_sha256"],
            "official_original_split": "TRAIN",
            "original_raw_measurement_text": raw,
            "processed_numeric_text": r["reported_ionic_conductivity_text"],
            "raw_measurement_kind": kind,
            "raw_total_component_text": original.get("IC (Total)", ""),
            "raw_bulk_component_text": original.get("IC (Bulk)", ""),
            "original_raw_workbook_sha256": _hash(blob),
            "raw_censor_upper_bound_is_a_point_value": False,
            "source_independent_truth_qualified": False,
        })
    if len(output) != queue["official_train_records_in_review"]:
        raise ValueError("original TRAIN records lost")
    if require_official and (
        counts["RAW_CENSORED"] != 37
        or counts["PROCESSED_1E_MINUS_15"] != 37
        or counts["RAW_CENSORED"] != counts["CENSORED_TRAIN"] + counts["CENSORED_TEST"]
    ):
        raise ValueError("original frozen 37-source censor mapping drift detected")
    output.sort(key=lambda row: row["source_entry_id"])
    output_blob = b"".join(_json_bytes(row) + b"\n" for row in output)
    report = {
        "schema_version": SCHEMA,
        "source_commit": pin,
        "original_raw_workbook_sha256": _hash(blob),
        "original_raw_workbook_size_bytes": len(blob),
        "original_workbook_sheet_header_columns": sorted(raw_columns),
        "original_workbook_record_count": len(raw_records),
        "processed_source_record_count": len(processed),
        "processed_numeric_floor_1e_minus_15_count": counts["PROCESSED_1E_MINUS_15"],
        "raw_upper_bound_count": counts["RAW_CENSORED"],
        "raw_positive_numeric_count": counts["RAW_NUMERIC"],
        "raw_unresolved_measurement_count": counts["RAW_UNRESOLVED"],
        "original_train_records": counts["ORIGINAL_TRAIN"],
        "original_test_records_reserved": counts["ORIGINAL_TEST"],
        "raw_train_censored_records": counts["CENSORED_TRAIN"],
        "raw_test_censored_records_reserved": counts["CENSORED_TEST"],
        "train_record_evidence_sha256": _hash(output_blob),
        "original_0131_train_worklist_sha256": queue["record_worklist_sha256"],
        "material_independence_verified_count": None,
        "new_scientifically_qualified_materials": 0,
        "new_external_blind_materials": 0,
        "scientific_verdict": "INDETERMINATE",
        "scientific_qualification_authorized": False,
        "limitations": [
            "RAW_UPPER_LIMIT_IS_NOT_POINT_MEASUREMENT",
            "1E_MINUS_15_IS_A_PREPROCESSING_SURROGATE_NOT_MEASURED_CONDUCTIVITY",
            "RAW_WORKBOOK_IS_CURATED_METADATA_NOT_INDEPENDENT_PAPER_ATTESTATION",
            "PUBLIC_TEST_RECORD_IDENTITIES_AND_LABELS_EXCLUDED_FROM_DEVELOPER_WORKLIST",
            "CENSOR_AWARE_METRIC_AND_TRAINING_POLICY_NOT_YET_IMPLEMENTED",
            "EXACT_MODEL_TRAINING_EXPOSURE_NOT_CERTIFIED",
        ],
    }
    return output, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--obelix-checkout", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        out = args.output_dir.resolve()
        if out.exists():
            raise ValueError("output destination must not pre-exist")
        source, evidence = args.obelix_checkout.resolve(strict=True), args.evidence_dir.resolve(strict=True)
        if out == source or source in out.parents or out == evidence or evidence in out.parents:
            raise ValueError("output cannot replace or dirty the original data")
        rows, report = build_original_censor_audit(source, evidence)
        out.mkdir(parents=True)
        (out / "train_raw_measurement_lineage.jsonl").write_bytes(
            b"".join(_json_bytes(row) + b"\n" for row in rows)
        )
        (out / "summary.json").write_bytes(_json_bytes(report) + b"\n")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
