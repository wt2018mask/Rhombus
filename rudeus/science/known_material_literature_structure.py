"""Deterministic literature-derived CIF reconstruction for ordered references.

This module never downloads or copies publisher structure files. It renders a small
ordered CIF from explicitly source-bound crystallographic facts stored in the artifact
registry, then validates that the rendered cell matches the declared composition and
space group.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Mapping

from rudeus.science.contracts import Record


LITERATURE_CIF_GENERATOR_VERSION = "literature-ordered-cif-v1"
LITERATURE_ASYMMETRIC_CIF_GENERATOR_VERSION = "literature-asymmetric-unit-cif-v1"
LITERATURE_FACT_RIGHTS_ID = "PROJECT-GENERATED-FROM-PUBLISHED-FACTS-v1"


def _formula_counts(value: str) -> dict[str, int]:
    tokens = re.findall(r"([A-Z][a-z]?)(\d*)", value.replace(" ", ""))
    if not tokens:
        raise ValueError("formula contains no element tokens")
    counts: dict[str, int] = {}
    for element, raw in tokens:
        count = int(raw or "1")
        counts[element] = counts.get(element, 0) + count
    return counts


@dataclass(frozen=True, kw_only=True)
class LiteratureCifRecipe(Record):
    generator_version: str
    source_ids: tuple[str, ...]
    phase_identity: str
    space_group_symbol: str
    space_group_number: int
    cell: Mapping[str, float]
    sites: tuple[Mapping[str, Any], ...]
    formula_units: int | None = None

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["source_ids"] = tuple(value["source_ids"])
        value["sites"] = tuple(dict(item) for item in value["sites"])
        return cls(**value)

    def validate(self):
        super().validate()
        if self.generator_version not in {
            LITERATURE_CIF_GENERATOR_VERSION,
            LITERATURE_ASYMMETRIC_CIF_GENERATOR_VERSION,
        }:
            raise ValueError("unsupported literature CIF generator version")
        if not self.source_ids or len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("literature CIF requires unique source identities")
        if not self.phase_identity or not self.space_group_symbol:
            raise ValueError("literature CIF phase identity is incomplete")
        if not 1 <= self.space_group_number <= 230:
            raise ValueError("invalid literature CIF space-group number")

        required = {"a", "b", "c", "alpha", "beta", "gamma"}
        if set(self.cell) != required:
            raise ValueError("literature CIF cell must define six lattice parameters")
        if any(float(self.cell[k]) <= 0 for k in ("a", "b", "c")):
            raise ValueError("literature CIF cell lengths must be positive")
        if any(not 0 < float(self.cell[k]) < 180 for k in ("alpha", "beta", "gamma")):
            raise ValueError("literature CIF cell angles must be between 0 and 180")

        asymmetric = (
            self.generator_version
            == LITERATURE_ASYMMETRIC_CIF_GENERATOR_VERSION
        )
        if asymmetric:
            if self.formula_units is None or int(self.formula_units) <= 0:
                raise ValueError(
                    "asymmetric literature CIF requires positive formula_units"
                )
        elif self.formula_units is not None:
            raise ValueError(
                "ordered full-cell literature CIF does not accept formula_units"
            )

        labels: set[str] = set()
        for site in self.sites:
            needed = {"label", "element", "x", "y", "z", "occupancy"}
            if asymmetric:
                needed = needed | {"multiplicity"}
            if set(site) != needed:
                raise ValueError("literature CIF site schema mismatch")
            label = str(site["label"])
            element = str(site["element"])
            if not label or not re.fullmatch(r"[A-Z][a-z]?", element):
                raise ValueError("literature CIF site identity invalid")
            if label in labels:
                raise ValueError("literature CIF site labels must be unique")
            labels.add(label)
            for key in ("x", "y", "z"):
                coord = float(site[key])
                if not 0 <= coord < 1:
                    raise ValueError("literature CIF fractional coordinate out of range")
            if float(site["occupancy"]) != 1.0:
                raise ValueError("ordered literature CIF requires full occupancy")
            if asymmetric:
                multiplicity = int(site["multiplicity"])
                if multiplicity <= 0 or float(site["multiplicity"]) != multiplicity:
                    raise ValueError(
                        "asymmetric literature CIF requires integer multiplicity"
                    )
        if not self.sites:
            raise ValueError("literature CIF requires atomic sites")


def render_literature_cif(
    recipe: LiteratureCifRecipe,
    *,
    data_name: str,
    expected_formula: str,
    expected_space_group_number: int,
) -> bytes:
    if recipe.space_group_number != expected_space_group_number:
        raise ValueError("literature CIF space group differs from registry validation")

    expected = _formula_counts(expected_formula)
    render_sites: list[dict[str, Any]]

    if recipe.generator_version == LITERATURE_CIF_GENERATOR_VERSION:
        observed: dict[str, int] = {}
        for site in recipe.sites:
            element = str(site["element"])
            observed[element] = observed.get(element, 0) + 1
        if observed != expected:
            raise ValueError(
                "literature CIF site multiplicities differ from expected formula"
            )
        render_sites = [dict(site) for site in recipe.sites]
    else:
        weighted: dict[str, int] = {}
        for site in recipe.sites:
            element = str(site["element"])
            weighted[element] = weighted.get(element, 0) + int(
                site["multiplicity"]
            )
        expected_cell = {
            element: count * int(recipe.formula_units)
            for element, count in expected.items()
        }
        if weighted != expected_cell:
            raise ValueError(
                "asymmetric literature CIF multiplicities differ from "
                "expected formula units"
            )
        # CIF atom-site rows are the source-bound asymmetric unit. The
        # declared space group expands them on read; writing a pre-expanded
        # full cell under the same non-P1 symmetry would apply symmetry twice.
        render_sites = [dict(site) for site in recipe.sites]

    safe_name = re.sub(r"[^A-Za-z0-9_]+", "_", data_name).strip("_")
    lines = [
        f"data_{safe_name}",
        f"_audit_creation_method '{recipe.generator_version}'",
        f"_chemical_formula_sum '{expected_formula}'",
        f"_cell_length_a {float(recipe.cell['a']):.10g}",
        f"_cell_length_b {float(recipe.cell['b']):.10g}",
        f"_cell_length_c {float(recipe.cell['c']):.10g}",
        f"_cell_angle_alpha {float(recipe.cell['alpha']):.10g}",
        f"_cell_angle_beta {float(recipe.cell['beta']):.10g}",
        f"_cell_angle_gamma {float(recipe.cell['gamma']):.10g}",
        f"_space_group_name_H-M_alt '{recipe.space_group_symbol}'",
        f"_space_group_IT_number {recipe.space_group_number}",
    ]
    lines.extend(f"# source_id {source_id}" for source_id in recipe.source_ids)
    lines.extend([
        "loop_",
        "_atom_site_label",
        "_atom_site_type_symbol",
    ])
    if recipe.generator_version == LITERATURE_ASYMMETRIC_CIF_GENERATOR_VERSION:
        lines.append("_atom_site_symmetry_multiplicity")
    lines.extend([
        "_atom_site_fract_x",
        "_atom_site_fract_y",
        "_atom_site_fract_z",
        "_atom_site_occupancy",
    ])
    for site in render_sites:
        prefix = f"{site['label']} {site['element']} "
        if recipe.generator_version == LITERATURE_ASYMMETRIC_CIF_GENERATOR_VERSION:
            prefix += f"{int(site['multiplicity'])} "
        lines.append(
            prefix
            + f"{float(site['x']):.10g} {float(site['y']):.10g} "
            + f"{float(site['z']):.10g} 1"
        )
    payload = ("\n".join(lines) + "\n").encode("utf-8")

    if recipe.generator_version == LITERATURE_ASYMMETRIC_CIF_GENERATOR_VERSION:
        # Round-trip through the project runtime parser so a source-table or
        # symmetry mistake fails before the artifact can be retained.
        from io import StringIO
        from pymatgen.io.cif import CifParser

        parsed = CifParser(StringIO(payload.decode("utf-8"))).parse_structures(
            primitive=False
        )
        if len(parsed) != 1:
            raise ValueError("asymmetric literature CIF did not parse uniquely")
        structure = parsed[0]
        actual: dict[str, int] = {}
        for site in structure:
            element = str(site.specie)
            actual[element] = actual.get(element, 0) + 1
        expected_cell = {
            element: count * int(recipe.formula_units)
            for element, count in expected.items()
        }
        if actual != expected_cell or len(structure) != sum(expected_cell.values()):
            raise ValueError(
                "asymmetric literature CIF round-trip composition mismatch"
            )

    return payload


def literature_cif_sha256(payload: bytes) -> str:
    if not payload:
        raise ValueError("literature CIF payload is empty")
    return hashlib.sha256(payload).hexdigest()
