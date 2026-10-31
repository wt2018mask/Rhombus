"""Byte-only pinning of exactly four TRAIN BVSE-initial XYZ members.

This never parses an XYZ record, reads relaxed DFT images, or decodes target
values. It merely supplies exact uncompressed member-byte hashes to the
non-executable Tier-A cost draft. A source hash is owner-byte continuity only.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import os
import stat
import zipfile

from .tier_a_preflight import ZIP_BYTES, ZIP_SHA256
from .tier_a_budget_contract import inspect_budget_draft, _sha

SCHEMA = "rhombus-0204-tier-a-initial-xyz-byte-binding-v1"
MAX_INIT_XYZ_BYTES = 8 * 1024 * 1024
MAX_TOTAL_INIT_XYZ_BYTES = 32 * 1024 * 1024


def _verify_owner_zip(path: Path) -> None:
    path = Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size != ZIP_BYTES:
        raise ValueError("OWNER_ZIP_BYTES_NOT_VERIFIED")
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != ZIP_SHA256:
        raise ValueError("OWNER_ZIP_SHA256_NOT_VERIFIED")


def pin_train_initial_xyz_bytes(draft: dict, archive: Path) -> tuple[dict, dict]:
    """Return a NEW pinned (still non-executable) draft and byte-only receipt.

    Reject already-pinned drafts, archive mismatch, ambiguous members, oversized
    members, encryption and nonregular file types. No extraction onto disk.
    """
    status = inspect_budget_draft(draft)
    if status["execution_authorized"] is not False:
        raise ValueError("RUN_AUTHORITY_FORBIDDEN")
    if any(edge["initial_images_sha256"] is not None for edge in draft["edges"]):
        raise ValueError("DO_NOT_REPIN_EXISTING_INPUTS")
    _verify_owner_zip(Path(archive))
    changed = deepcopy(draft)
    identities = []
    total = 0
    with zipfile.ZipFile(archive, "r") as z:
        for edge in changed["edges"]:
            name = f'nebDFT2k/{edge["edge_id"]}_init.xyz'
            matches = [info for info in z.infolist() if info.filename == name]
            if len(matches) != 1:
                raise ValueError("INITIAL_XYZ_MISSING_OR_DUPLICATED")
            info = matches[0]
            mode = (info.external_attr >> 16) & 0o170000
            if (info.is_dir() or info.flag_bits & 1 or
                mode not in (0, stat.S_IFREG) or
                not 0 < info.file_size <= MAX_INIT_XYZ_BYTES or
                info.compress_size > MAX_INIT_XYZ_BYTES):
                raise ValueError("UNSAFE_INITIAL_XYZ_MEMBER")
            total += info.file_size
            if total > MAX_TOTAL_INIT_XYZ_BYTES:
                raise ValueError("INITIAL_XYZ_TOTAL_BYTE_BUDGET")
            digest = sha256()
            read_bytes = 0
            with z.open(info, "r") as handle:
                for chunk in iter(lambda: handle.read(64 * 1024), b""):
                    read_bytes += len(chunk)
                    if read_bytes > MAX_INIT_XYZ_BYTES:
                        raise ValueError("INITIAL_XYZ_DECOMPRESSED_TOO_LARGE")
                    digest.update(chunk)
            if read_bytes != info.file_size:
                raise ValueError("INITIAL_XYZ_SIZE_MISMATCH")
            file_hash = digest.hexdigest()
            edge["initial_images_sha256"] = file_hash
            identities.append({"edge_id": edge["edge_id"], "group_id": edge["group_id"],
                               "zip_member": name, "raw_uncompressed_bytes": read_bytes,
                               "raw_uncompressed_sha256": file_hash})
    state = inspect_budget_draft(changed)
    if "INITIAL_IMAGE_HASHES_MISSING" in state["blockers"]:
        raise ValueError("INITIAL_INPUT_PINNING_INCOMPLETE")
    receipt = {
        "schema_version": SCHEMA,
        "archive_owner_sha256": ZIP_SHA256,
        "publisher_authenticity": "UNATTESTED",
        "archive_size_bytes": ZIP_BYTES,
        "operation": "SHA256_OF_ONLY_FOUR_INITIAL_XYZ_UNCOMPRESSED_MEMBER_BYTES_NO_XYZ_PARSE",
        "relaxed_dft_xyz_access": "NONE",
        "target_columns_access": "NONE",
        "initial_member_count": len(identities),
        "initial_total_uncompressed_bytes": total,
        "identities": identities,
        "prior_draft_sha256": status["draft_sha256"],
        "pinned_draft_sha256": state["draft_sha256"],
        "execution_authorized": False,
        "scientific_status": "SCIENTIFIC_NO_GO_ABSTAIN",
        "benchmark_status": "BENCHMARK_NOT_FROZEN",
    }
    return changed, receipt
