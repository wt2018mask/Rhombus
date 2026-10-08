"""Inspect a bounded downloaded diagnostic ZIP and bind it to local receipt bytes.

ZIP-to-local-byte equality is NOT proof that GitHub issued the archive.
The upstream Figshare source and MACE-MPA-0 training set remain unattested.
"""
from __future__ import annotations

from hashlib import sha256
import hmac
import io
import json
import re
from pathlib import Path
import stat
import zipfile

from rhombus.domain.mptrj_probe_receipt import validate_mptrj_first_frame_receipt

ARTIFACT_ENTRY = "mptrj-first-frame-observation.json"
MAX_ARCHIVE_BYTES = 64 * 1024
MAX_RECEIPT_BYTES = 16 * 1024
ARTIFACT_DIGEST_PATTERN = re.compile(r"sha256:([0-9a-f]{64})\Z")


class MPTrjArtifactZipError(ValueError):
    """Untrusted or mismatching bounded diagnostic artifact archive."""


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    out = {}
    for key, value in pairs:
        if key in out:
            raise MPTrjArtifactZipError("duplicate JSON key in bound diagnostic receipt")
        out[key] = value
    return out


def _bounded_file(path: Path, limit: int, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise MPTrjArtifactZipError(f"{label} must be a regular non-symlink file")
    if not 1 <= path.stat().st_size <= limit:
        raise MPTrjArtifactZipError(f"{label} outside bounded byte budget")
    with path.open("rb") as fh:
        data = fh.read(limit + 1)
    if not 1 <= len(data) <= limit:
        raise MPTrjArtifactZipError(f"{label} exceeds bounded byte budget")
    return data


def verify_mptrj_diagnostic_zip_binding(
    artifact_zip_path: Path,
    local_receipt_path: Path,
    *,
    expected_prefix_bytes: int = 262144,
    expected_artifact_digest: str | None = None,
) -> dict:
    """Reject unsafe archive entries; hash exact receipt bytes from both sources.

    The ZIP file and local receipt are independently supplied by the operator.
    This proves equality of *those local copies only*, not authenticated origin.
    """
    # One bounded ZIP byte snapshot is both hashed and parsed.
    zip_raw = _bounded_file(artifact_zip_path, MAX_ARCHIVE_BYTES, "artifact ZIP")
    zip_sha256 = sha256(zip_raw).hexdigest()
    if expected_artifact_digest is not None:
        if not isinstance(expected_artifact_digest, str) or not ARTIFACT_DIGEST_PATTERN.fullmatch(expected_artifact_digest):
            raise MPTrjArtifactZipError("expected artifact digest must be canonical sha256:lowercase-hex")
        if not hmac.compare_digest(zip_sha256, expected_artifact_digest.removeprefix("sha256:")):
            raise MPTrjArtifactZipError("ZIP SHA256 does not match caller-supplied GitHub artifact digest")
    local_raw = _bounded_file(local_receipt_path, MAX_RECEIPT_BYTES, "local receipt")
    try:
        with zipfile.ZipFile(io.BytesIO(zip_raw), "r") as archive:
            files = archive.infolist()
            if len(files) != 1:
                raise MPTrjArtifactZipError("archive must contain exactly one diagnostic entry")
            entry = files[0]
            if entry.filename != ARTIFACT_ENTRY or entry.is_dir():
                raise MPTrjArtifactZipError("archive entry name/path is not the expected report")
            if entry.flag_bits & 1:
                raise MPTrjArtifactZipError("encrypted ZIP entry is prohibited")
            mode = stat.S_IFMT(entry.external_attr >> 16)
            if mode not in (0, stat.S_IFREG):
                raise MPTrjArtifactZipError("nonregular or symlink ZIP entry is prohibited")
            if not 1 <= entry.file_size <= MAX_RECEIPT_BYTES:
                raise MPTrjArtifactZipError("uncompressed receipt exceeds 16KiB limit")
            if entry.compress_size > MAX_ARCHIVE_BYTES:
                raise MPTrjArtifactZipError("compressed member exceeds bounded ZIP budget")
            with archive.open(entry, "r") as source:
                archived_raw = source.read(MAX_RECEIPT_BYTES + 1)
            if len(archived_raw) != entry.file_size:
                raise MPTrjArtifactZipError("member payload mismatches declared size")
    except (zipfile.BadZipFile, EOFError, RuntimeError, NotImplementedError) as exc:
        raise MPTrjArtifactZipError("invalid or unsupported diagnostic ZIP") from exc

    archive_digest = sha256(archived_raw).digest()
    local_digest = sha256(local_raw).digest()
    if not hmac.compare_digest(archive_digest, local_digest):
        raise MPTrjArtifactZipError("local receipt bytes differ from artifact ZIP member")
    record = json.loads(archived_raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    validated = validate_mptrj_first_frame_receipt(record, expected_prefix_bytes=expected_prefix_bytes)
    return {
        "status": "LOCAL_ARTIFACT_ZIP_RECEIPT_BYTES_MATCH_ONLY",
        "receipt_byte_sha256": archive_digest.hex(),
        "artifact_zip_sha256": zip_sha256,
        "matches_caller_supplied_artifact_digest": expected_artifact_digest is not None,
        "receipt_metadata_sha256": validated["report_metadata_sha256"],
        "github_archive_origin_authenticated": False,
        "github_api_response_authenticated": False,
        "full_source_byte_identity_verified": False,
        "model_training_frame_membership_attested": False,
        "execute_exposure_audit": False,
        "empirical_calibration_use": False,
        "unseen_generalization_claim": False,
    }
