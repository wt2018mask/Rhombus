"""Offline-verifiable import contract for public COD structure artifacts.

Network transport is intentionally kept outside the scientific contract. A caller may
retrieve the pinned COD URL by any ordinary HTTP client, but Rhombus only accepts the
bytes after the COD identity, revision-scoped source specification, formula, space
group, coordinate payload, and SHA256 can be checked locally.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import os
from pathlib import Path
import re
import tempfile

from rudeus.science.contracts import Record, require_hash
from rudeus.science.known_material_structure_binding import (
    LicenseDisposition,
    StructureArtifactState,
    StructureBindingLedger,
)


COD_BASE = "https://www.crystallography.net/cod"
COD_LICENSE = "CC0-1.0"
COD_IMPORT_VERSION = "known-material-cod-import-v1"


@dataclass(frozen=True, kw_only=True)
class CodArtifactSpec(Record):
    material_key: str
    cod_id: str
    revision: int
    expected_formula: str
    expected_space_group_number: int

    def validate(self):
        super().validate()
        if not self.material_key:
            raise ValueError("COD import requires material key")
        if not (self.cod_id.isdigit() and len(self.cod_id) == 7):
            raise ValueError("COD id must be a seven-digit identifier")
        if self.revision <= 0:
            raise ValueError("COD revision must be positive")
        if not self.expected_formula:
            raise ValueError("COD import requires expected formula")
        if not 1 <= self.expected_space_group_number <= 230:
            raise ValueError("invalid crystallographic space-group number")

    @property
    def source_id(self) -> str:
        return f"cod:{self.cod_id}@{self.revision}"

    @property
    def pinned_locator(self) -> str:
        return f"{COD_BASE}/{self.cod_id}.cif@{self.revision}"


@dataclass(frozen=True, kw_only=True)
class CodRetentionReceipt(Record):
    import_version: str
    material_key: str
    source_id: str
    pinned_locator: str
    license_id: str
    artifact_sha256: str
    byte_count: int
    retained_path: str
    expected_formula: str
    expected_space_group_number: int

    def validate(self):
        super().validate()
        if self.import_version != COD_IMPORT_VERSION:
            raise ValueError("unsupported COD import receipt version")
        if not all((self.material_key, self.source_id, self.pinned_locator,
                    self.license_id, self.retained_path, self.expected_formula)):
            raise ValueError("COD retention receipt identity incomplete")
        if self.license_id != COD_LICENSE:
            raise ValueError("COD receipt must preserve CC0 identity")
        require_hash(self.artifact_sha256)
        if self.byte_count <= 0:
            raise ValueError("COD receipt requires nonempty retained bytes")
        if not 1 <= self.expected_space_group_number <= 230:
            raise ValueError("invalid receipt space-group number")


def sha256_bytes(payload: bytes) -> str:
    if not payload:
        raise ValueError("structure artifact is empty")
    return hashlib.sha256(payload).hexdigest()


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1].strip()
    return value


def _scalar(text: str, names: tuple[str, ...]) -> str | None:
    for name in names:
        pattern = re.compile(
            rf"(?im)^\s*{re.escape(name)}\s+([^\r\n]+?)\s*$"
        )
        match = pattern.search(text)
        if match:
            return _unquote(match.group(1))
    return None


def _formula_key(value: str) -> tuple[tuple[str, str], ...]:
    tokens = re.findall(r"([A-Z][a-z]?)([-+]?(?:\d+(?:\.\d*)?|\.\d+)?)", value)
    if not tokens:
        raise ValueError("formula contains no element tokens")
    normalized = []
    for element, count in tokens:
        normalized.append((element, count or "1"))
    return tuple(sorted(normalized))


def verify_cod_cif_payload(payload: bytes, spec: CodArtifactSpec) -> str:
    """Validate retained COD bytes and return their SHA256.

    This is deliberately a byte-preserving check: validation never rewrites the CIF.
    """
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("COD CIF must be UTF-8 decodable") from exc

    cod_id = _scalar(text, ("_cod_database_code",))
    if cod_id != spec.cod_id:
        raise ValueError("COD CIF database identity mismatch")

    formula = _scalar(text, ("_chemical_formula_sum", "_cod_original_formula_sum"))
    if formula is None or _formula_key(formula) != _formula_key(spec.expected_formula):
        raise ValueError("COD CIF formula mismatch")

    sg = _scalar(
        text,
        (
            "_space_group_IT_number",
            "_symmetry_Int_Tables_number",
        ),
    )
    if sg is None:
        raise ValueError("COD CIF lacks space-group number")
    try:
        sg_number = int(float(sg.split()[0]))
    except ValueError as exc:
        raise ValueError("COD CIF has invalid space-group number") from exc
    if sg_number != spec.expected_space_group_number:
        raise ValueError("COD CIF space-group mismatch")

    required_coordinate_tags = (
        "_atom_site_fract_x",
        "_atom_site_fract_y",
        "_atom_site_fract_z",
    )
    if any(tag.lower() not in text.lower() for tag in required_coordinate_tags):
        raise ValueError("COD CIF lacks fractional atomic coordinates")

    return sha256_bytes(payload)


def retain_cod_cif_payload(
    payload: bytes,
    spec: CodArtifactSpec,
    destination: str | Path,
) -> CodRetentionReceipt:
    """Verify then atomically retain exact CIF bytes without normalization."""
    digest = verify_cod_cif_payload(payload, spec)
    path = Path(destination)
    if path.suffix.lower() != ".cif":
        raise ValueError("retained COD artifact must use .cif extension")
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise

    retained = path.read_bytes()
    if retained != payload or sha256_bytes(retained) != digest:
        raise ValueError("retained COD artifact differs from verified input bytes")

    return CodRetentionReceipt(
        import_version=COD_IMPORT_VERSION,
        material_key=spec.material_key,
        source_id=spec.source_id,
        pinned_locator=spec.pinned_locator,
        license_id=COD_LICENSE,
        artifact_sha256=digest,
        byte_count=len(payload),
        retained_path=path.as_posix(),
        expected_formula=spec.expected_formula,
        expected_space_group_number=spec.expected_space_group_number,
    )


def apply_cod_retention_receipt(
    ledger: StructureBindingLedger,
    receipt: CodRetentionReceipt,
) -> StructureBindingLedger:
    """Promote exactly one matching COD binding to ARTIFACT_RETAINED.

    Scientific validation is intentionally not granted here: material-specific
    representation blockers survive this transition.
    """
    matches = [
        (index, entry)
        for index, entry in enumerate(ledger.entries)
        if entry.material_key == receipt.material_key
    ]
    if len(matches) != 1:
        raise ValueError("COD receipt must match exactly one structure binding")
    index, entry = matches[0]

    if entry.source_id != receipt.source_id:
        raise ValueError("COD receipt source identity differs from structure ledger")
    if entry.artifact_locator != receipt.pinned_locator:
        raise ValueError("COD receipt locator differs from structure ledger")
    if entry.license_disposition != LicenseDisposition.VERIFIED_REDISTRIBUTABLE.value:
        raise ValueError("COD retention requires verified redistribution rights")
    if entry.expected_format.upper() != "CIF":
        raise ValueError("COD retention requires CIF structure binding")
    if entry.artifact_state == StructureArtifactState.HASHED_AND_VALIDATED.value:
        raise ValueError("validated structure cannot be replaced by retention workflow")
    if entry.artifact_state == StructureArtifactState.REJECTED.value:
        raise ValueError("rejected structure cannot be retained without new curation")
    if entry.artifact_sha256 not in (None, receipt.artifact_sha256):
        raise ValueError("existing structure hash conflicts with COD receipt")
    if entry.retained_path not in (None, receipt.retained_path):
        raise ValueError("existing retained path conflicts with COD receipt")

    blockers = tuple(
        blocker for blocker in entry.blockers
        if blocker != "artifact_not_yet_retained_and_hashed"
    )
    retained = replace(
        entry,
        artifact_state=StructureArtifactState.ARTIFACT_RETAINED.value,
        artifact_sha256=receipt.artifact_sha256,
        retained_path=receipt.retained_path,
        blockers=blockers,
    )
    entries = list(ledger.entries)
    entries[index] = retained
    return replace(ledger, entries=tuple(entries))
