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
LITERATURE_ASYMMETRIC_CIF_GENERATOR_VERSION = "literature-asymmetric-cif-v1"
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

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["source_ids"] = tuple(value["source_ids"])
        value["sites"] = tuple(dict(item) for item in value["sites"])
        return cls(**value)

    def validate(self):
        super().validate()
        if self.generator_version != LITERATURE_CIF_GENERATOR_VERSION:
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

        labels: set[str] = set()
        for site in self.sites:
            needed = {"label", "element", "x", "y", "z", "occupancy"}
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

    observed: dict[str, int] = {}
    for site in recipe.sites:
        element = str(site["element"])
        observed[element] = observed.get(element, 0) + 1
    if observed != _formula_counts(expected_formula):
        raise ValueError("literature CIF site multiplicities differ from expected formula")

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
        "_atom_site_fract_x",
        "_atom_site_fract_y",
        "_atom_site_fract_z",
        "_atom_site_occupancy",
    ])
    for site in recipe.sites:
        lines.append(
            f"{site['label']} {site['element']} "
            f"{float(site['x']):.10g} {float(site['y']):.10g} "
            f"{float(site['z']):.10g} 1"
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


def literature_cif_sha256(payload: bytes) -> str:
    if not payload:
        raise ValueError("literature CIF payload is empty")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, kw_only=True)
class LiteratureAsymmetricCifRecipe(Record):
    """Source-bound asymmetric-unit CIF recipe with explicit Wyckoff multiplicities."""

    generator_version: str
    source_ids: tuple[str, ...]
    phase_identity: str
    space_group_symbol: str
    space_group_number: int
    formula_units_z: int
    cell: Mapping[str, float]
    sites: tuple[Mapping[str, Any], ...]

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["source_ids"] = tuple(value["source_ids"])
        value["sites"] = tuple(dict(item) for item in value["sites"])
        return cls(**value)

    def validate(self):
        super().validate()
        if self.generator_version != LITERATURE_ASYMMETRIC_CIF_GENERATOR_VERSION:
            raise ValueError("unsupported asymmetric literature CIF generator version")
        if not self.source_ids or len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("asymmetric literature CIF requires unique source identities")
        if not self.phase_identity or not self.space_group_symbol:
            raise ValueError("asymmetric literature CIF phase identity is incomplete")
        if not 1 <= self.space_group_number <= 230:
            raise ValueError("invalid asymmetric literature CIF space-group number")
        if self.formula_units_z <= 0:
            raise ValueError("asymmetric literature CIF requires positive Z")

        required = {"a", "b", "c", "alpha", "beta", "gamma"}
        if set(self.cell) != required:
            raise ValueError("asymmetric literature CIF cell must define six lattice parameters")
        if any(float(self.cell[k]) <= 0 for k in ("a", "b", "c")):
            raise ValueError("asymmetric literature CIF cell lengths must be positive")
        if any(not 0 < float(self.cell[k]) < 180 for k in ("alpha", "beta", "gamma")):
            raise ValueError(
                "asymmetric literature CIF cell angles must be between zero and 180"
            )

        labels: set[str] = set()
        for site in self.sites:
            needed = {
                "label",
                "element",
                "x",
                "y",
                "z",
                "occupancy",
                "wyckoff_multiplicity",
                "wyckoff_symbol",
            }
            if set(site) != needed:
                raise ValueError("asymmetric literature CIF site schema mismatch")
            label = str(site["label"])
            element = str(site["element"])
            if not label or not re.fullmatch(r"[A-Z][a-z]?", element):
                raise ValueError("asymmetric literature CIF site identity invalid")
            if label in labels:
                raise ValueError("asymmetric literature CIF site labels must be unique")
            labels.add(label)
            for key in ("x", "y", "z"):
                coord = float(site[key])
                if not -1 < coord < 2:
                    raise ValueError(
                        "asymmetric literature CIF fractional coordinate outside bounded range"
                    )
            if float(site["occupancy"]) != 1.0:
                raise ValueError(
                    "asymmetric ordered literature CIF requires full occupancy"
                )
            multiplicity = int(site["wyckoff_multiplicity"])
            if multiplicity <= 0:
                raise ValueError("Wyckoff multiplicity must be positive")
            symbol = str(site["wyckoff_symbol"])
            if not re.fullmatch(r"[a-z]", symbol):
                raise ValueError("Wyckoff symbol must be one lowercase letter")
        if not self.sites:
            raise ValueError("asymmetric literature CIF requires atomic sites")


def render_asymmetric_literature_cif(
    recipe: LiteratureAsymmetricCifRecipe,
    *,
    data_name: str,
    expected_formula: str,
    expected_space_group_number: int,
) -> bytes:
    if recipe.space_group_number != expected_space_group_number:
        raise ValueError(
            "asymmetric literature CIF space group differs from registry validation"
        )

    expected = {
        element: count * recipe.formula_units_z
        for element, count in _formula_counts(expected_formula).items()
    }
    observed: dict[str, int] = {}
    for site in recipe.sites:
        element = str(site["element"])
        observed[element] = observed.get(element, 0) + int(
            site["wyckoff_multiplicity"]
        )
    if observed != expected:
        raise ValueError(
            "asymmetric literature CIF Wyckoff multiplicities differ from "
            "expected formula times Z"
        )

    safe_name = re.sub(r"[^A-Za-z0-9_]+", "_", data_name).strip("_")
    lines = [
        f"data_{safe_name}",
        f"_audit_creation_method '{recipe.generator_version}'",
        f"_chemical_formula_sum '{expected_formula}'",
        f"_cell_formula_units_Z {recipe.formula_units_z}",
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
        "_atom_site_symmetry_multiplicity",
        "_atom_site_Wyckoff_symbol",
        "_atom_site_fract_x",
        "_atom_site_fract_y",
        "_atom_site_fract_z",
        "_atom_site_occupancy",
    ])
    for site in recipe.sites:
        lines.append(
            f"{site['label']} {site['element']} "
            f"{int(site['wyckoff_multiplicity'])} {site['wyckoff_symbol']} "
            f"{float(site['x']):.10g} {float(site['y']):.10g} "
            f"{float(site['z']):.10g} 1"
        )
    return ("\n".join(lines) + "\n").encode("utf-8")
