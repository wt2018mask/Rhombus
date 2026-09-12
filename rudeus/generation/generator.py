"""G1 parent retrieval + local perturbation and G2 substitution operators.

Single-module generation stage (CPU-only):
  - Parent retrieval from OBELiX (all CIF-linked entries across the FULL
    dataset — generation is not benchmarking, so the train/test split
    restriction of rudeus.bench does not apply) and from LiIon where a
    structure can be attached. Every parent carries full provenance
    (source dataset, source ID/DOI, sha256 of the parent structure).
  - G1 operators: (a) atomic displacement, (b) lattice strain, (c) vacancy /
    interstitial on the mobile-ion sublattice. Magnitudes configurable,
    all PROVISIONAL.
  - G2 operator: heterovalent/isovalent substitution from a configurable
    allowlist, with SMACT charge-balance guidance from p0.py. Lives in this
    same module, not a separate code path.
  - Every child: parent ID + operator/params recorded, StructureMatcher
    comparison vs parent and vs already-generated siblings ("rediscovery" vs
    "novel" — local tags only, NOT MP/OQMD/JARVIS novelty, which belongs to
    the later [N] stage and needs external APIs).
  - Every child runs through P0 immediately at generation time. P0 FAILs are
    KEPT with existence_state=FAIL and the rejection reason attached, never
    dropped silently (raw generator hit rate stays visible).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from pymatgen.analysis.structure_matcher import StructureMatcher
from pymatgen.core import Composition, Element, Lattice, Structure
from pymatgen.transformations.standard_transformations import DeformStructureTransformation

from rudeus.empirical.liion import LiIonDataset
from rudeus.empirical.obelix import OBELiXDataset, classify_chemical_family, normalize_formula
from rudeus.filters.p0 import check_charge_neutrality_smact, evaluate_p0
from rudeus.schema import CandidateMaterial, EvidenceEvent, ExistenceState


# ---------------------------------------------------------------------------
# Provenance helpers
# ---------------------------------------------------------------------------
def structure_sha256(structure: Structure) -> str:
    """Deterministic sha256 over the structure's serialized dict."""
    payload = json.dumps(structure.as_dict(), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Parent records
# ---------------------------------------------------------------------------
@dataclass
class ParentRecord:
    """A retrieved parent structure with full provenance.

    Attributes:
        parent_id: Stable ID, e.g. "obelix:ro9" or "liion:123".
        source_dataset: "obelix" or "liion".
        source_ref: OBELiX entry ID, or LiIon "ID + DOI" string.
        composition: Composition string as published by the source dataset.
        structure: Pymatgen Structure, or None when the source ships none.
        structure_sha256: Hex digest of the parent structure ("" if none).
        conductivity: Published ionic conductivity in S/cm (None if unknown).
        chemical_family: Classified family (obelix) or ChemicalFamily (liion).
        perturbable: False when no structure is attached (retrievable, not
            perturbable) — such parents are skipped at generation with reason.
        provenance: Full provenance dict (dataset, refs, borrow records).
    """

    parent_id: str
    source_dataset: str
    source_ref: str
    composition: str
    structure: Optional[Structure]
    structure_sha256: str
    conductivity: Optional[float]
    chemical_family: str
    perturbable: bool
    provenance: Dict[str, Any] = field(default_factory=dict)


def retrieve_obelix_parents(repo_path: Union[str, Path]) -> List[ParentRecord]:
    """Retrieve all CIF-linked OBELiX entries (full dataset, train AND test).

    Generation is not benchmarking: the bench split restriction does not apply.
    Deterministic order (sorted IDs). Structures that fail to parse are kept
    as non-perturbable records with the parse failure recorded (never dropped).
    """
    dataset = OBELiXDataset(repo_path)
    cond_col = "Ionic conductivity (S cm-1)"
    parents: List[ParentRecord] = []
    for entry_id in sorted(dataset.df["ID"].astype(str).tolist()):
        cif_path = dataset.cif_dir / f"{entry_id}.cif"
        if not cif_path.exists():
            continue
        row = dataset.df[dataset.df["ID"] == entry_id].iloc[0]
        try:
            struct = Structure.from_file(str(cif_path))
        except Exception as e:  # keep record, mark non-perturbable
            parents.append(ParentRecord(
                parent_id=f"obelix:{entry_id}",
                source_dataset="obelix",
                source_ref=entry_id,
                composition=str(row["Composition"]),
                structure=None,
                structure_sha256="",
                conductivity=float(row[cond_col]),
                chemical_family=str(row.get("chemical_family", "unknown")),
                perturbable=False,
                provenance={"source": "obelix", "cif": str(cif_path),
                            "parse_error": str(e)},
            ))
            continue
        parents.append(ParentRecord(
            parent_id=f"obelix:{entry_id}",
            source_dataset="obelix",
            source_ref=entry_id,
            composition=str(row["Composition"]),
            structure=struct,
            structure_sha256=structure_sha256(struct),
            conductivity=float(row[cond_col]),
            chemical_family=str(row.get("chemical_family", "unknown")),
            perturbable=True,
            provenance={"source": "obelix", "cif": str(cif_path),
                        "structure_sha256": structure_sha256(struct)},
        ))
    return parents


def retrieve_liion_parents(
    csv_path: Union[str, Path],
    obelix_repo: Union[str, Path],
) -> List[ParentRecord]:
    """Retrieve LiIon rows as parents; attach a structure only where available.

    LiIon ships NO structures. A structure handle is borrowed from the OBELiX
    CIF whose normalized formula exactly matches (same mechanism as the bench
    cross-check, with the borrow recorded in provenance). Rows without a match
    are still returned (composition + conductivity + DOI provenance) but marked
    non-perturbable. Tables are never merged — only a structure handle is read.
    """
    liion = LiIonDataset(csv_path)
    obelix = OBELiXDataset(obelix_repo)
    cif_ids = {p.stem for p in obelix.cif_dir.glob("*.cif")} if obelix.cif_dir.exists() else set()
    formula_map: Dict[str, str] = {}
    for _, orow in obelix.df.iterrows():
        oid = str(orow["ID"])
        if oid not in cif_ids:
            continue
        try:
            key = normalize_formula(str(orow["Composition"]))
        except Exception:
            continue
        if key not in formula_map or oid < formula_map[key]:
            formula_map[key] = oid

    parents: List[ParentRecord] = []
    for _, row in liion.df.iterrows():
        lid = str(row["ID"])
        comp = str(row["composition"])
        try:
            key = normalize_formula(comp)
        except Exception:
            key = None
        oid = formula_map.get(key) if key else None
        struct = obelix.get_structure(oid) if oid else None
        if struct is not None:
            prov = {"source": "liion", "liion_id": lid,
                    "doi": str(row.get("source", "")),
                    "borrowed_structure_from": f"obelix:{oid}",
                    "structure_sha256": structure_sha256(struct)}
            parents.append(ParentRecord(
                parent_id=f"liion:{lid}",
                source_dataset="liion",
                source_ref=f"{lid} doi:{row.get('source', '')}",
                composition=comp,
                structure=struct,
                structure_sha256=structure_sha256(struct),
                conductivity=float(row["target"]),
                chemical_family=str(row.get("ChemicalFamily", "unknown")),
                perturbable=True,
                provenance=prov,
            ))
        else:
            parents.append(ParentRecord(
                parent_id=f"liion:{lid}",
                source_dataset="liion",
                source_ref=f"{lid} doi:{row.get('source', '')}",
                composition=comp,
                structure=None,
                structure_sha256="",
                conductivity=float(row["target"]),
                chemical_family=str(row.get("ChemicalFamily", "unknown")),
                perturbable=False,
                provenance={"source": "liion", "liion_id": lid,
                            "doi": str(row.get("source", "")),
                            "reason": "no structure shipped; no formula match"},
            ))
    return parents


# ---------------------------------------------------------------------------
# Operator helpers (occupancy-aware site selection)
# ---------------------------------------------------------------------------
def _site_symbols(site) -> set:
    species = site.species
    if hasattr(species, "elements"):
        return {el.symbol for el in species.elements}
    return {species.symbol}


def _site_dominant_symbol(site) -> str:
    species = site.species
    if hasattr(species, "elements"):
        return max(species.elements, key=lambda el: float(species[el])).symbol
    return species.symbol


def _mobile_site_indices(structure: Structure, mobile_ion: str) -> List[int]:
    return [i for i, s in enumerate(structure) if mobile_ion in _site_symbols(s)]


# ---------------------------------------------------------------------------
# G1 operators — each returns (new_structure, applied_params)
# ---------------------------------------------------------------------------
def op_displace(
    structure: Structure,
    rng: np.random.Generator,
    sigma_A_provisional: float = 0.05,
) -> Tuple[Structure, Dict[str, Any]]:
    """(a) Independent Gaussian displacement of every site (Cartesian, PROVISIONAL sigma)."""
    new_struct = structure.copy()
    for i in range(len(new_struct)):
        shift = rng.normal(0.0, sigma_A_provisional, size=3)
        new_struct.translate_sites(i, shift, frac_coords=False)
    return new_struct, {"operator": "displace",
                        "sigma_A_provisional": sigma_A_provisional}


def op_strain(
    structure: Structure,
    rng: np.random.Generator,
    strain_max_fraction_provisional: float = 0.02,
) -> Tuple[Structure, Dict[str, Any]]:
    """(b) Random symmetric lattice strain, uniform in [-max, +max] (PROVISIONAL)."""
    rand = rng.uniform(-strain_max_fraction_provisional,
                       strain_max_fraction_provisional, size=(3, 3))
    symm = (rand + rand.T) / 2.0
    deformation = np.eye(3) + symm
    new_struct = DeformStructureTransformation(deformation).apply_transformation(structure)
    return new_struct, {"operator": "strain",
                        "strain_max_fraction_provisional": strain_max_fraction_provisional,
                        "deformation": deformation.tolist()}


def op_vacancy(
    structure: Structure,
    rng: np.random.Generator,
    mobile_ion: str = "Li",
) -> Tuple[Structure, Dict[str, Any]]:
    """(c1) Remove one random mobile-ion site (whole site incl. mixed occupancy)."""
    candidates = _mobile_site_indices(structure, mobile_ion)
    if not candidates:
        raise ValueError(f"op_vacancy: no {mobile_ion}-containing site to vacate")
    idx = int(rng.choice(candidates))
    removed = _site_dominant_symbol(structure[idx])
    new_struct = structure.copy()
    new_struct.remove_sites([idx])
    return new_struct, {"operator": "vacancy", "mobile_ion": mobile_ion,
                        "site_index": idx, "removed_species": removed}


def op_interstitial(
    structure: Structure,
    rng: np.random.Generator,
    mobile_ion: str = "Li",
) -> Tuple[Structure, Dict[str, Any]]:
    """(c2) Insert one mobile ion at a uniform-random fractional position."""
    new_struct = structure.copy()
    frac = rng.uniform(0.0, 1.0, size=3).tolist()
    new_struct.append(mobile_ion, frac, coords_are_cartesian=False)
    return new_struct, {"operator": "interstitial", "mobile_ion": mobile_ion,
                        "frac_coords": frac}


# ---------------------------------------------------------------------------
# G2 operator — heterovalent/isovalent substitution (same module, same registry)
# ---------------------------------------------------------------------------
def op_substitute(
    structure: Structure,
    rng: np.random.Generator,
    allowed_swaps: Dict[str, List[str]],
    mobile_ion: str = "Li",
) -> Tuple[Structure, Dict[str, Any]]:
    """G2: substitute one site with an allowlisted alternative.

    Eligibility: sites whose dominant element is a key in allowed_swaps.
    The swap is ALWAYS applied (even heterovalent); charge balance of the
    resulting formula is then checked with SMACT guidance from p0.py and
    recorded — P0 at generation time delivers the verdict (kept either way).
    """
    eligible = [i for i, s in enumerate(structure)
                if _site_dominant_symbol(s) in allowed_swaps]
    if not eligible:
        raise ValueError("op_substitute: no site with an allowlisted element")
    idx = int(rng.choice(eligible))
    old_el = _site_dominant_symbol(structure[idx])
    new_el = str(rng.choice(allowed_swaps[old_el]))
    new_struct = structure.copy()
    new_struct[idx] = new_el  # ordered substitution, recorded as such
    formula = str(new_struct.composition.reduced_formula)
    neutral_ok, neut_details = check_charge_neutrality_smact(formula)
    return new_struct, {"operator": "substitute",
                        "site_index": idx, "old_element": old_el,
                        "new_element": new_el,
                        "result_formula": formula,
                        "smact_neutral": bool(neutral_ok),
                        "smact_details": neut_details}


# ---------------------------------------------------------------------------
# G1/G2 family labels (explicit per-child provenance; operator semantics unchanged)
# ---------------------------------------------------------------------------
G2_OPERATORS = frozenset({"substitute"})


def operator_family(op_name: str) -> str:
    """G1 vs G2 family label for an operator name (G2 = substitution)."""
    return "G2" if op_name in G2_OPERATORS else "G1"


OPERATORS = {
    "displace": op_displace,
    "strain": op_strain,
    "vacancy": op_vacancy,
    "interstitial": op_interstitial,
    "substitute": op_substitute,  # G2 lives in the same registry
}


# ---------------------------------------------------------------------------
# Generation driver: child records, novelty tags, P0 at birth
# ---------------------------------------------------------------------------
def _child_id(parent_id: str, ops: List[Dict[str, Any]], child: Structure) -> str:
    payload = json.dumps({"parent": parent_id, "ops": ops,
                          "struct": child.as_dict()}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def generate_children(
    parent: ParentRecord,
    operators: Sequence[str],
    children_per_parent: int,
    seed: int,
    matcher: Optional[StructureMatcher] = None,
    allowed_swaps: Optional[Dict[str, List[str]]] = None,
    displacement_sigma_A_provisional: float = 0.05,
    strain_max_fraction_provisional: float = 0.02,
    mobile_ion: str = "Li",
    defect_modes: Sequence[str] = ("vacancy", "interstitial"),
    matcher_ltol_provisional: float = 0.2,
    matcher_stol_provisional: float = 0.3,
    matcher_angle_tol_provisional: float = 5.0,
    generation_config_hash: Optional[str] = None,
) -> List[CandidateMaterial]:
    """Generate children from one parent, tag novelty, run P0 at birth.

    Non-perturbable parents yield zero children (callers record the skip).
    Operator per child is sampled by rng from `operators` ("defect" samples
    from `defect_modes`). Deterministic given `seed`. Novelty tolerances are
    the calibrated PROVISIONAL config values (see config.yaml `generation.matcher`).

    Provenance recorded per child (metadata): parent ID + composition +
    provenance, G1/G2 family, operator name + params, seed, child index,
    generation config hash (when supplied), P0 verdict + details, novelty
    tag. material_id covers (parent_id, ops, structure) only — metadata
    additions never change existing IDs.
    """
    if not parent.perturbable or parent.structure is None:
        return []
    rng = np.random.default_rng(seed)
    matcher = matcher or StructureMatcher(
        ltol=matcher_ltol_provisional,
        stol=matcher_stol_provisional,
        angle_tol=matcher_angle_tol_provisional,
    )
    siblings: List[Structure] = []
    children: List[CandidateMaterial] = []

    for child_index in range(children_per_parent):
        op_name = str(rng.choice(list(operators)))
        if op_name == "defect":
            op_name = str(rng.choice(list(defect_modes)))
        try:
            if op_name == "displace":
                child_struct, op_params = op_displace(
                    parent.structure, rng, displacement_sigma_A_provisional)
            elif op_name == "strain":
                child_struct, op_params = op_strain(
                    parent.structure, rng, strain_max_fraction_provisional)
            elif op_name == "vacancy":
                child_struct, op_params = op_vacancy(
                    parent.structure, rng, mobile_ion)
            elif op_name == "interstitial":
                child_struct, op_params = op_interstitial(
                    parent.structure, rng, mobile_ion)
            elif op_name == "substitute":
                child_struct, op_params = op_substitute(
                    parent.structure, rng, allowed_swaps or {}, mobile_ion)
            else:
                raise ValueError(f"unknown operator {op_name!r}")
            op_error = None
        except Exception as e:  # operator inapplicable: keep a FAIL child, never crash
            child_struct, op_params = parent.structure.copy(), {"operator": op_name}
            op_error = f"{type(e).__name__}: {e}"

        formula = str(child_struct.composition.reduced_formula)
        child_id = _child_id(parent.parent_id, [op_params], child_struct)

        # Novelty vs parent, then vs already-generated siblings (local tags only).
        matcher_note = None
        try:
            if matcher.fit(parent.structure, child_struct):
                novelty = "rediscovery"
                matched = "parent"
            else:
                matched = None
                for sib in siblings:
                    if matcher.fit(sib, child_struct):
                        matched = "sibling"
                        break
                novelty = "rediscovery" if matched else "novel"
        except Exception as e:
            novelty, matched = "novel", None
            matcher_note = f"matcher-error: {type(e).__name__}: {e}"
        siblings.append(child_struct)

        candidate = CandidateMaterial(
            material_id=f"g1-{child_id}",
            formula=formula,
            structure_dict=child_struct.as_dict(),
            metadata={
                "parent_id": parent.parent_id,
                "parent_composition": parent.composition,
                "parent_provenance": parent.provenance,
                "family": operator_family(op_params.get("operator", op_name)),
                "operators": [op_params],
                "operator_error": op_error,
                "seed": seed,
                "child_index": child_index,
                "generation_config_hash": generation_config_hash,
                "novelty_tag": novelty,
                "novelty_matched": matched,
                "matcher_note": matcher_note,
                "matcher_tolerances_provisional": {
                    "ltol": matcher_ltol_provisional,
                    "stol": matcher_stol_provisional,
                    "angle_tol": matcher_angle_tol_provisional,
                },
            },
        )
        # P0 immediately at generation time — FAILs kept with reason attached.
        p0 = evaluate_p0(formula, structure=child_struct)
        candidate.add_evidence(
            p0.evidence_event,
            new_existence_state=p0.existence_state,
        )
        candidate.metadata["p0_passed"] = p0.passed
        candidate.metadata["p0_details"] = {
            "neutrality_ok": p0.neutrality_ok,
            "pauling_ok": p0.pauling_ok,
            "geometry_ok": p0.geometry_ok,
            "details": p0.details,
        }
        if not p0.passed:
            candidate.metadata["p0_rejection"] = {
                "neutrality_ok": p0.neutrality_ok,
                "pauling_ok": p0.pauling_ok,
                "geometry_ok": p0.geometry_ok,
            }
        children.append(candidate)
    return children
