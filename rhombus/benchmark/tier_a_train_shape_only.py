"""Bounded shape-only reading of four preselected TRAIN initial XYZ members.

This diagnostic does not inspect coordinates, comment metadata, per-atom numeric
fields, relaxed DFT images, or energy targets. The initial source can contain
energy and force attributes; they are intentionally treated as opaque bytes.

Identity of the four paths must be checked *before* calling this function with
verify_pilot_input_binding() against the owner-provided pinned cost draft.
ZIP and member SHA256 checks establish byte continuity, not authenticity.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import os
import re
import stat
import zipfile
from typing import Mapping

from .tier_a_preflight import ZIP_BYTES, ZIP_SHA256
from .tier_a_input_pin import MAX_INIT_XYZ_BYTES

SCHEMA = "rhombus-0205-tier-a-train-init-xyz-shape-only-v1"
MAX_LINE_BYTES = 16_384
MAX_FRAMES = 16
MAX_ATOMS_PER_FRAME = 4096
MAX_TOTAL_BYTES = 32 * 1024 * 1024
_SOURCE_PATTERN = re.compile(r"nebDFT2k/(mp-[0-9]+_[0-9_-]+)_init\.xyz\Z")
_SPECIES_PATTERN = re.compile(rb"[A-Z][a-z]?\Z")
_SHA_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def _check_hash(value: str) -> None:
    if type(value) is not str or _SHA_PATTERN.fullmatch(value) is None:
        raise ValueError("EXPECTED_SHA256_REQUIRED")


def _read_bounded_line(stream, digest, tracker: list[int]) -> bytes:
    line = stream.readline(MAX_LINE_BYTES + 1)
    if len(line) > MAX_LINE_BYTES:
        raise ValueError("XYZ_LINE_TOO_LONG")
    tracker[0] += len(line)
    if tracker[0] > MAX_INIT_XYZ_BYTES:
        raise ValueError("XYZ_UNCOMPRESSED_BYTE_BUDGET")
    digest.update(line)
    return line


def _parse_member(stream) -> tuple[int, int, int, int, str, int]:
    """Read only atom-count lines and species tokens; never parse numeric payloads."""
    digest = sha256()
    count = [0]
    nframes = 0
    n_atoms = None
    first_species = None
    n_li = None
    while True:
        header = _read_bounded_line(stream, digest, count)
        if not header:
            break
        if not re.fullmatch(rb"[1-9][0-9]{0,5}\r?\n?", header):
            raise ValueError("XYZ_ATOM_COUNT_INVALID")
        n = int(header.strip())
        if n > MAX_ATOMS_PER_FRAME:
            raise ValueError("XYZ_ATOM_BUDGET_EXCEEDED")
        if nframes >= MAX_FRAMES:
            raise ValueError("XYZ_FRAME_BUDGET_EXCEEDED")
        # This line may contain E, forces, stress, model results etc. NEVER decode it.
        if not _read_bounded_line(stream, digest, count):
            raise ValueError("XYZ_COMMENT_LINE_TRUNCATED")
        species = []
        for _ in range(n):
            raw = _read_bounded_line(stream, digest, count)
            if not raw:
                raise ValueError("XYZ_ATOM_BLOCK_TRUNCATED")
            symbol = raw.split(maxsplit=1)[0]
            if _SPECIES_PATTERN.fullmatch(symbol) is None:
                raise ValueError("XYZ_SPECIES_TOKEN_INVALID")
            # Everything after the first token is opaque, even if it contains labels.
            species.append(symbol)
        frozen = tuple(species)
        if first_species is None:
            n_atoms, first_species = n, frozen
            n_li = frozen.count(b"Li")
            if n_li == 0:
                raise ValueError("XYZ_LI_ABSENT")
        elif n != n_atoms or frozen != first_species:
            raise ValueError("XYZ_ATOM_COUNT_OR_SPECIES_ORDER_MISMATCH")
        nframes += 1
    if not nframes:
        raise ValueError("XYZ_NO_FRAMES")
    return nframes, n_atoms, n_li, count[0], digest.hexdigest(), len(set(first_species))


def scan_pinned_train_initial_shapes(
    *, archive: Path, identities: list[Mapping[str, object]],
    archive_sha256: str = ZIP_SHA256, archive_size_bytes: int = ZIP_BYTES,
) -> dict[str, object]:
    """Verify an exact four-record source manifest and report shape metadata.

    Caller MUST verify identities against the full unmodified draft/receipt
    before the report may be described as a selected TRAIN pilot. Tests can
    supply a synthetic archive identity; that never authenticates an owner ZIP.
    """
    _check_hash(archive_sha256)
    if type(archive_size_bytes) is not int or archive_size_bytes <= 0:
        raise ValueError("INVALID_ARCHIVE_SIZE")
    if type(identities) is not list or len(identities) != 4:
        raise ValueError("EXACT_FOUR_PINNED_INPUTS_REQUIRED")
    expected: dict[str, tuple[str, int, str]] = {}
    groups: set[str] = set()
    for rec in identities:
        if type(rec) is not dict or set(rec) != {
            "edge_id", "group_id", "zip_member", "raw_uncompressed_bytes",
            "raw_uncompressed_sha256",
        }:
            raise ValueError("INPUT_IDENTITY_EXACT_FIELDS_REQUIRED")
        name = rec["zip_member"]
        if type(name) is not str:
            raise ValueError("INPUT_MEMBER_NAME_INVALID")
        m = _SOURCE_PATTERN.fullmatch(name)
        if (m is None or rec["edge_id"] != m.group(1) or
                type(rec["group_id"]) is not str or
                not rec["group_id"].startswith("CHEMSYS:") or
                len(rec["group_id"]) > 80):
            raise ValueError("UNSAFE_OR_MISMATCHED_INPUT_PATH")
        size = rec["raw_uncompressed_bytes"]
        if type(size) is not int or not 0 < size <= MAX_INIT_XYZ_BYTES:
            raise ValueError("INITIAL_MEMBER_SIZE_INVALID")
        _check_hash(rec["raw_uncompressed_sha256"])
        if name in expected or rec["group_id"] in groups:
            raise ValueError("DUPLICATE_MEMBER_OR_CHEMISTRY_GROUP")
        expected[name] = (rec["raw_uncompressed_sha256"], size, rec["group_id"])
        groups.add(rec["group_id"])
    path = Path(archive)
    if path.is_symlink() or not path.is_file():
        raise ValueError("ARCHIVE_UNTRUSTED_SIZE_OR_TYPE")
    # Hash and parse through ONE file descriptor; do not open a fresh path
    # after verifying its digest (race-prone for replaceable file paths).
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    reports = []
    total_uncompressed = 0
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size != archive_size_bytes:
            raise ValueError("ARCHIVE_UNTRUSTED_SIZE_OR_TYPE")
        with os.fdopen(fd, "rb", closefd=False) as fh:
            h = sha256()
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
            if h.hexdigest() != archive_sha256:
                raise ValueError("ARCHIVE_SHA256_MISMATCH")
            fh.seek(0)
            with zipfile.ZipFile(fh) as z:
                for name, (expected_sha, expected_bytes, group_id) in sorted(expected.items()):
                    members = [i for i in z.infolist() if i.filename == name]
                    if len(members) != 1:
                        raise ValueError("MISSING_OR_DUPLICATED_INITIAL_MEMBER")
                    info = members[0]
                    mode = (info.external_attr >> 16) & 0o170000
                    if (info.is_dir() or info.flag_bits & 1 or mode not in (0, stat.S_IFREG)
                            or info.file_size != expected_bytes or
                            not 0 < info.file_size <= MAX_INIT_XYZ_BYTES):
                        raise ValueError("UNSAFE_OR_MISMATCHED_ZIP_MEMBER")
                    total_uncompressed += info.file_size
                    if total_uncompressed > MAX_TOTAL_BYTES:
                        raise ValueError("TOTAL_INITIAL_INPUT_BYTES_EXCEEDED")
                    with z.open(info) as member_stream:
                        frames, atoms, li, nread, observed_sha, kinds = _parse_member(member_stream)
                    if nread != expected_bytes or observed_sha != expected_sha:
                        raise ValueError("INITIAL_MEMBER_SHA256_OR_LENGTH_MISMATCH")
                    reports.append({"edge_id": name.removeprefix("nebDFT2k/").removesuffix("_init.xyz"),
                                    "group_id": group_id, "initial_frames": frames,
                                    "atoms_per_frame": atoms, "lithium_atoms_per_frame": li,
                                    "distinct_element_types": kinds,
                                    "same_atom_count_and_species_order_all_frames": True})
        after = os.fstat(fd)
        if ((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                != (before.st_dev, before.st_ino, before.st_size,
                    before.st_mtime_ns, before.st_ctime_ns)):
            raise ValueError("ARCHIVE_CHANGED_DURING_AUDIT")
    finally:
        os.close(fd)
    return {
        "schema_version": SCHEMA,
        "reference_scope": "FOUR_PRESELECTED_TRAIN_INITIAL_IMAGES_ONLY",
        "source_identity": "BYTE_CONTINUITY_NOT_PUBLISHER_AUTHENTICITY",
        "member_count": len(reports),
        "initial_total_uncompressed_bytes": total_uncompressed,
        "shape_rows": reports,
        "per_atom_energy_or_force_values_decoded": False,
        "xyz_comment_fields_decoded": False,
        "positions_decoded": False,
        "relaxed_or_heldout_inputs_opened": False,
        "single_li_hop_physically_verified": False,
        "scientific_status": "SCIENTIFIC_NO_GO_ABSTAIN",
        "benchmark_status": "BENCHMARK_NOT_FROZEN",
        "execution_authorized": False,
    }


def audit_owner_train_shape_only(*, archive: Path, draft: dict,
                                 input_binding_receipt: dict) -> dict[str, object]:
    """Require source/train identity binding before shape-only scanning."""
    from .tier_a_model_neb_preflight import verify_pilot_input_binding
    verify_pilot_input_binding(draft, input_binding_receipt)
    return scan_pinned_train_initial_shapes(
        archive=archive, identities=input_binding_receipt["identities"])
