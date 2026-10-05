"""Offline-verifiable primitives for COD CIF artifacts.

This module is source-specific by design: it knows how COD identifies and encodes a
CIF, but it does not plan benchmark work, retain repository files, or mutate ledgers.
Those responsibilities belong to the generic artifact-curation layer.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from rudeus.science.contracts import Record


COD_BASE = "https://www.crystallography.net/cod"
COD_LICENSE = "CC0-1.0"


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
    return tuple(sorted((element, count or "1") for element, count in tokens))


def verify_cod_cif_payload(payload: bytes, spec: CodArtifactSpec) -> str:
    """Validate exact COD CIF bytes and return their SHA256."""
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
