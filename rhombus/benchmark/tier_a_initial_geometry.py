"""Tier A offline geometry-only audit of four pinned TRAIN initial NEB XYZ.

Only species, Cartesian positions, lattice and PBC are decoded. Header energy,
free_energy, stress, and trailing per-atom energies/forces remain opaque bytes.
Not physical NEB validation; not a calculator, scorer, or execution authority.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from hashlib import sha256
import math
import os
from pathlib import Path
import re
import stat
import zipfile

from .tier_a_budget_contract import _sha, inspect_budget_draft
from .tier_a_input_pin import MAX_INIT_XYZ_BYTES
from .tier_a_model_neb_preflight import verify_pilot_input_binding
from .tier_a_preflight import ZIP_SHA256, ZIP_BYTES

SCHEMA = "rhombus-0205-tier-a-train-initial-geometry-diagnostic-v1"
MAX_ATOMS = 8192
MAX_IMAGES = 7
MAX_LINE = 16384
PARSER_SCOPE = "ONLY_SPECIES_POSITION_LATTICE_PBC_NO_ENERGY_FORCE_STRESS"
LATTICE = re.compile(rb'(?<![A-Za-z0-9_])Lattice="([^"]+)"')
PROPERTIES = re.compile(rb'(?<![A-Za-z0-9_])Properties=([^\s"]+)')
PBC = re.compile(rb'(?<![A-Za-z0-9_])pbc="([^"]+)"')
SYMBOL = re.compile(rb'[A-Z][a-z]?\Z')


def _one(header: bytes, pattern: re.Pattern[bytes], name: str) -> bytes:
    hits = pattern.findall(header)
    if len(hits) != 1:
        raise ValueError(f"{name}_MISSING_OR_AMBIGUOUS")
    return hits[0]


def _cell(header: bytes) -> tuple[tuple[float, ...], float]:
    pieces = _one(header, LATTICE, "LATTICE").split()
    if len(pieces) != 9:
        raise ValueError("LATTICE_NINE_COMPONENTS_REQUIRED")
    try:
        c = tuple(float(x) for x in pieces)
    except (ValueError, OverflowError) as exc:
        raise ValueError("INVALID_LATTICE_FLOAT") from exc
    if not all(math.isfinite(x) for x in c):
        raise ValueError("NONFINITE_LATTICE")
    a,b,c2,d,e,f,g,h,i = c
    volume = a*(e*i-f*h)-b*(d*i-f*g)+c2*(d*h-e*g)
    if volume == 0 or not math.isfinite(volume):
        raise ValueError("SINGULAR_OR_NONFINITE_LATTICE")
    return c, abs(volume)


def inspect_initial_xyz_geometry(blob: bytes) -> dict:
    """Bounded, geometry-only extended XYZ inspection; no label decoding."""
    if type(blob) is not bytes or not 0 < len(blob) <= MAX_INIT_XYZ_BYTES:
        raise ValueError("INITIAL_XYZ_TYPE_OR_BYTE_BUDGET")
    lines = blob.splitlines()
    offset, images = 0, 0
    reference_species = reference_cell = first = previous = None
    counts = None
    max_step = max_li_step = max_li_end = 0.0
    volume = None
    while offset < len(lines):
        if images >= MAX_IMAGES:
            raise ValueError("TOO_MANY_IMAGES")
        nfield = lines[offset]
        if len(nfield) > 10 or not nfield.isdigit() or not 0 < int(nfield) <= MAX_ATOMS:
            raise ValueError("INVALID_ATOM_COUNT")
        n = int(nfield)
        if offset + n + 2 > len(lines):
            raise ValueError("TRUNCATED_IMAGE")
        header = lines[offset + 1]
        if len(header) > MAX_LINE:
            raise ValueError("OVERSIZED_HEADER")
        props = _one(header, PROPERTIES, "PROPERTIES")
        if not (props == b"species:S:1:pos:R:3" or
                props.startswith(b"species:S:1:pos:R:3:")):
            raise ValueError("UNSUPPORTED_GEOMETRY_COLUMN_POSITION")
        if _one(header, PBC, "PBC").split() != [b"T", b"T", b"T"]:
            raise ValueError("NONPERIODIC_INITIAL_IMAGE")
        cell, vol = _cell(header)
        if reference_cell is None:
            reference_cell, volume = cell, vol
        elif cell != reference_cell:
            raise ValueError("LATTICE_CHANGED_ACROSS_IMAGES")
        species, xyz = [], []
        for line in lines[offset + 2: offset + 2 + n]:
            if not line or len(line) > MAX_LINE:
                raise ValueError("MALFORMED_ATOM_ROW")
            # Additional energy/force/stress columns remain opaque byte tail.
            cols = line.split(None, 4)
            if len(cols) < 4 or SYMBOL.fullmatch(cols[0]) is None:
                raise ValueError("UNSUPPORTED_SPECIES_OR_MISSING_POSITION")
            try:
                coordinates = tuple(float(x) for x in cols[1:4])
            except (ValueError, OverflowError) as exc:
                raise ValueError("INVALID_COORDINATE_FLOAT") from exc
            if not all(math.isfinite(x) for x in coordinates):
                raise ValueError("NONFINITE_POSITION")
            species.append(cols[0].decode("ascii"))
            xyz.append(coordinates)
        if reference_species is None:
            reference_species = tuple(species)
            if "Li" not in species:
                raise ValueError("NO_LITHIUM_IN_INITIAL_IMAGE")
            counts = dict(sorted(Counter(species).items()))
            first = xyz
        elif tuple(species) != reference_species:
            raise ValueError("SPECIES_OR_ATOM_ORDER_CHANGED")
        if previous is not None:
            for symbol, x, y in zip(species, previous, xyz):
                value = math.dist(x, y)
                max_step = max(max_step, value)
                if symbol == "Li":
                    max_li_step = max(max_li_step, value)
        for symbol, x, y in zip(species, first, xyz):
            if symbol == "Li":
                max_li_end = max(max_li_end, math.dist(x, y))
        previous = xyz
        images += 1
        offset += n + 2
    if images not in (5, 7):
        raise ValueError("INITIAL_NEB_IMAGE_COUNT_NOT_FIVE_OR_SEVEN")
    return {
        "images": images, "atoms_per_image": len(reference_species),
        "species_counts": counts, "cell_volume_A3": volume,
        "periodic_all_axes": True, "fixed_lattice": True,
        "fixed_atom_species_order": True,
        "max_direct_consecutive_atom_A": max_step,
        "max_direct_consecutive_Li_A": max_li_step,
        "max_direct_first_to_last_Li_A": max_li_end,
        "distance_qualification":
            "DIRECT_CARTESIAN_DIAGNOSTIC_NOT_PBC_UNWRAPPED_NOT_HOP_BARRIER",
        "decoded_fields": PARSER_SCOPE,
    }


@contextmanager
def _open_pinned_archive(path: Path):
    """Verify the same regular file descriptor subsequently used by ZipFile."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError("OWNER_ZIP_SYMLINK_REJECTED")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as raw:
        before = os.fstat(raw.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size != ZIP_BYTES:
            raise ValueError("OWNER_ZIP_BYTES_NOT_VERIFIED")
        h = sha256()
        for chunk in iter(lambda: raw.read(1024 * 1024), b""):
            h.update(chunk)
        pinned = os.fstat(raw.fileno())
        if (h.hexdigest() != ZIP_SHA256 or
                (before.st_size, before.st_mtime_ns, before.st_ctime_ns) !=
                (pinned.st_size, pinned.st_mtime_ns, pinned.st_ctime_ns)):
            raise ValueError("OWNER_ZIP_SHA256_NOT_VERIFIED")
        raw.seek(0)
        with zipfile.ZipFile(raw, "r") as archive:
            yield archive
        after = os.fstat(raw.fileno())
        if ((pinned.st_size, pinned.st_mtime_ns, pinned.st_ctime_ns) !=
                (after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
            raise ValueError("OWNER_ZIP_CHANGED_DURING_AUDIT")


def audit_pinned_train_initial_geometry(*, draft: dict, receipt: dict,
                                        owner_zip: Path) -> dict:
    """Read ONLY the four sealed-by-SHA TRAIN *_init.xyz members."""
    contract = inspect_budget_draft(draft)
    if contract["execution_authorized"] is not False:
        raise ValueError("UNAUTHORIZED_RUN_STATE")
    verify_pilot_input_binding(draft, receipt)
    rows = []
    with _open_pinned_archive(Path(owner_zip)) as archive:
        for edge in draft["edges"]:
            member = f'nebDFT2k/{edge["edge_id"]}_init.xyz'
            matches = [m for m in archive.infolist() if m.filename == member]
            if len(matches) != 1:
                raise ValueError("TRAIN_INITIAL_MEMBER_MISSING_OR_DUPLICATE")
            info = matches[0]
            mode = (info.external_attr >> 16) & 0o170000
            if (info.flag_bits & 1 or info.is_dir() or
                    mode not in (0, stat.S_IFREG) or
                    not 0 < info.file_size <= MAX_INIT_XYZ_BYTES or
                    info.compress_size > MAX_INIT_XYZ_BYTES):
                raise ValueError("UNSAFE_TRAIN_INITIAL_MEMBER")
            with archive.open(info) as stream:
                raw = stream.read(MAX_INIT_XYZ_BYTES + 1)
            if (len(raw) != info.file_size or
                    sha256(raw).hexdigest() != edge["initial_images_sha256"]):
                raise ValueError("TRAIN_INITIAL_MEMBER_BYTE_IDENTITY_MISMATCH")
            rows.append({"edge_id": edge["edge_id"], "group_id": edge["group_id"],
                         "raw_initial_xyz_sha256": edge["initial_images_sha256"],
                         **inspect_initial_xyz_geometry(raw)})
    rows.sort(key=lambda item: item["edge_id"])
    return {
        "schema_version": SCHEMA,
        "reference_archive_owner_sha256": ZIP_SHA256,
        "contract_sha256": _sha(draft),
        "source_claim": "OWNER_PROVIDED_BYTES_UNATTESTED_PUBLISHER_SIGNATURE",
        "operation": "FOUR_TRAIN_INITIAL_GEOMETRIES_ONLY",
        "relaxed_dft_xyz_access": "NONE",
        "validation_test_member_access": "NONE",
        "energy_and_force_metadata_parsing": "NONE",
        "target_scoring": "NOT_PERFORMED",
        "pilot_rows": rows,
        "all_structural_parsers_passed": True,
        "physical_neb_path_validity": "NOT_ESTABLISHED",
        "training_overlap": "UNKNOWN",
        "benchmark_status": "BENCHMARK_NOT_FROZEN",
        "scientific_status": "SCIENTIFIC_NO_GO_ABSTAIN",
        "execution_authorized": False,
    }
