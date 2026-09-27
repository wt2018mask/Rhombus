"""Tests for rudeus.generation (G1 perturbation + G2 substitution, small fixtures)."""

import json
from pathlib import Path

import numpy as np
import pytest
from pymatgen.core import Lattice, Structure

import rudeus.generation
from rudeus.filters.p0 import evaluate_p0
from rudeus.generation import (
    ParentRecord,
    audit_parent_selection,
    generate_children,
    op_displace,
    op_interstitial,
    op_strain,
    op_substitute,
    op_vacancy,
    retrieve_liion_parents,
    retrieve_obelix_parents,
)
from rudeus.schema import ExistenceState


def _licl():
    lattice = Lattice.cubic(4.0)
    return Structure(lattice, ["Li", "Cl"], [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])


def _parent(struct=None):
    s = struct or _licl()
    return ParentRecord(
        parent_id="test:licl", source_dataset="test", source_ref="licl",
        composition="LiCl", structure=s, structure_sha256="abc",
        conductivity=None, chemical_family="halide", perturbable=True,
        provenance={"source": "test"},
    )


def test_generation_module_namespace():
    """Verify generation package is importable and has docstring."""
    assert rudeus.generation.__doc__ is not None
    assert "G1 Generation" in rudeus.generation.__doc__
    assert "G2 Generation" in rudeus.generation.__doc__


def test_no_bvse_in_generation_or_mlip_code():
    """F2/BVSE is REMOVED: no reference may exist in the active code path."""
    import rudeus.generation
    import rudeus.mlip

    for pkg in (rudeus.generation, rudeus.mlip):
        pkg_dir = Path(pkg.__file__).parent
        for py in sorted(pkg_dir.glob("*.py")):
            src = py.read_text(encoding="utf-8").lower()
            assert "bvse" not in src, f"BVSE reference in active path: {py}"


def _stub_kid(op, family, parent, formula, p0_pass, novelty,
              matched=None, matcher_note=None, rej=None, op_error=None):
    from rudeus.schema import CandidateMaterial, ExistenceState

    meta = {
        "parent_id": parent,
        "parent_composition": "LiCl",
        "family": family,
        "operators": [{"operator": op}],
        "operator_error": op_error,
        "seed": 42,
        "child_index": 0,
        "generation_config_hash": "abc123",
        "novelty_tag": novelty,
        "novelty_matched": matched,
        "matcher_note": matcher_note,
        "p0_passed": p0_pass,
        "p0_details": {"neutrality_ok": True, "pauling_ok": True,
                       "geometry_ok": p0_pass, "details": {}},
    }
    if not p0_pass:
        meta["p0_rejection"] = rej or {"neutrality_ok": False,
                                       "geometry_ok": True}
    return CandidateMaterial(
        material_id=f"t-{op}-{parent}-{formula}", formula=formula,
        existence_state=(ExistenceState.PLAUSIBLE if p0_pass
                         else ExistenceState.FAIL),
        metadata=meta,
    )


def test_audit_counts_all_distributions():
    """Audit reports operator/parent/family/P0/novelty counts faithfully."""
    from rudeus.generation import audit_candidates

    kids = [
        _stub_kid("displace", "G1", "obelix:a", "LiCl", True, "novel"),
        _stub_kid("strain", "G1", "obelix:a", "LiCl", True, "rediscovery",
                  matched="parent"),
        _stub_kid("vacancy", "G1", "obelix:b", "Cl", False, "novel",
                  rej={"neutrality_ok": False, "geometry_ok": True}),
        _stub_kid("substitute", "G2", "obelix:b", "NaCl", False, "novel",
                  matched=None, matcher_note="matcher-error: X",
                  rej={"neutrality_ok": True, "geometry_ok": False}),
        _stub_kid("substitute", "G2", "obelix:b", "NaCl", True,
                  "rediscovery", matched="sibling"),
    ]
    report = audit_candidates(kids)
    assert report["total"] == 5
    assert report["g1_g2"] == {"G1": 3, "G2": 2}
    assert report["operators"] == {"displace": 1, "strain": 1, "vacancy": 1,
                                   "substitute": 2}
    assert report["unique_parents"] == 2
    assert report["per_parent"] == {"obelix:a": 2, "obelix:b": 3}
    assert report["p0"] == {"passed": 3, "rejected": 2}
    assert report["p0_rejection_reasons"] == {"neutrality": 1, "geometry": 1}
    assert report["novelty"]["novel"] == 2  # displace + vacancy children
    assert report["novelty"]["rediscovery-parent"] == 1
    assert report["novelty"]["rediscovery-sibling"] == 1
    assert report["novelty"]["novel-matcher-error"] == 1
    assert sum(report["novelty"].values()) == 5
    assert set(report["parent_families"]) == {"halide"}
    assert set(report["child_families"]) >= {"halide"}



def test_parent_selection_audit_is_descriptive_and_exposes_high_conductivity_omissions():
    parents = [
        ParentRecord(
            parent_id="p:a", source_dataset="test", source_ref="a",
            composition="LiCl", structure=_licl(), structure_sha256="a",
            conductivity=1.0e-5, chemical_family="halide", perturbable=True,
            provenance={},
        ),
        ParentRecord(
            parent_id="p:b", source_dataset="test", source_ref="b",
            composition="LiCl", structure=_licl(), structure_sha256="b",
            conductivity=2.0e-2, chemical_family="halide", perturbable=True,
            provenance={},
        ),
        ParentRecord(
            parent_id="p:c", source_dataset="test", source_ref="c",
            composition="LiCl", structure=_licl(), structure_sha256="c",
            conductivity=None, chemical_family="halide", perturbable=True,
            provenance={},
        ),
    ]
    report = audit_parent_selection(parents, ["p:a"], top_unselected=5)
    assert report["diagnostic_only"] is True
    assert report["selection_policy_changed"] is False
    assert report["n_perturbable_parents"] == 3
    assert report["n_ordered_parents"] == 3
    assert report["n_selected_parents"] == 1
    assert report["n_with_published_conductivity"] == 2
    assert report["n_ordered_with_published_conductivity"] == 2
    assert report["selected_conductivity"] == {
        "n": 1, "min": 1.0e-5, "median": 1.0e-5, "max": 1.0e-5
    }
    assert report["unselected_conductivity"]["max"] == 2.0e-2
    assert report["top_unselected_by_published_conductivity"][0]["parent_id"] == "p:b"

def _structures_equal(a, b):
    import json
    return (json.dumps(a.as_dict(), sort_keys=True, default=str)
            == json.dumps(b.as_dict(), sort_keys=True, default=str))


def test_operators_deterministic_given_seed():
    """Same seed -> bit-identical children.

    Different seeds must differ for continuous operators (displace/strain/
    interstitial). Vacancy is a discrete single-site choice that may coincide
    legitimately, so only same-seed equality is asserted for it.
    """
    for op, kwargs, must_differ in [
        (op_displace, {"sigma_A_provisional": 0.05}, True),
        (op_strain, {"strain_max_fraction_provisional": 0.02}, True),
        (op_vacancy, {}, False),
        (op_interstitial, {}, True),
    ]:
        a, _ = op(_licl(), np.random.default_rng(7), **kwargs)
        b, _ = op(_licl(), np.random.default_rng(7), **kwargs)
        c, _ = op(_licl(), np.random.default_rng(8), **kwargs)
        assert _structures_equal(a, b)
        if must_differ:
            assert not _structures_equal(a, c)


def test_operator_effects_on_composition_and_lattice():
    """Each operator does what its name claims."""
    base = _licl()
    rng = np.random.default_rng(0)

    strained, _ = op_strain(base, rng, 0.02)
    assert not np.allclose(strained.lattice.matrix, base.lattice.matrix)
    assert strained.composition.reduced_formula == "LiCl"

    vac, params = op_vacancy(base, rng)
    assert len(vac) == len(base) - 1
    assert params["removed_species"] == "Li"

    inter, _ = op_interstitial(base, rng)
    assert len(inter) == len(base) + 1
    assert inter.composition["Li"] == base.composition["Li"] + 1

    sub, params = op_substitute(base, rng, {"Li": ["Na"]})
    assert "Na" in {el.symbol for el in sub.composition.elements}
    assert "Li" not in {el.symbol for el in sub.composition.elements}
    assert params["old_element"] == "Li" and params["new_element"] == "Na"
    assert isinstance(params["smact_neutral"], bool)

    with pytest.raises(ValueError):
        op_vacancy(base, rng, mobile_ion="Mg")  # no Mg site to vacate


def test_absurd_displacement_trips_p0_clash():
    """Heavily perturbed structure must FAIL P0 on geometry, not pass silently.

    A 2-atom cell can dodge a clash by luck, so the test forces one overlap
    deterministically after a heavy operator-path displacement.
    """
    rng = np.random.default_rng(1)
    wrecked, _ = op_displace(_licl(), rng, sigma_A_provisional=2.5)
    wrecked.translate_sites(0, wrecked[1].coords - wrecked[0].coords,
                            frac_coords=False)  # site 0 lands on site 1
    res = evaluate_p0("LiCl", structure=wrecked)
    assert res.geometry_ok is False
    assert res.passed is False
    assert res.existence_state == ExistenceState.FAIL
    assert res.details["geometry"].get("clash_detected") is True


def test_child_provenance_complete_and_deterministic():
    """Same parent/seed/config -> identical children with full provenance.

    Single-operator runs keep the test deterministic by construction (no
    dependence on which operator a seed happens to sample).
    """
    def run(ops, seed):
        return generate_children(
            _parent(), operators=ops, children_per_parent=2, seed=seed,
            generation_config_hash="ghash1",
            allowed_swaps={"Li": ["Na"]},
            displacement_sigma_A_provisional=0.05)

    g1_a, g1_b = run(["displace"], 11), run(["displace"], 11)
    g2_a, g2_b = run(["substitute"], 12), run(["substitute"], 12)
    assert [k.material_id for k in g1_a] == [k.material_id for k in g1_b]
    assert [k.material_id for k in g2_a] == [k.material_id for k in g2_b]
    for ka, kb in zip(g1_a + g2_a, g1_b + g2_b):
        assert ka.metadata == kb.metadata  # full provenance deterministic

    assert all(k.metadata["family"] == "G1" for k in g1_a)
    assert all(k.metadata["family"] == "G2" for k in g2_a)
    for j, kid in enumerate(g1_a + g2_a):
        meta = kid.metadata
        assert meta["parent_id"] == "test:licl"
        assert meta["parent_composition"] == "LiCl"
        assert meta["seed"] in (11, 12)
        assert meta["child_index"] == j % 2
        assert meta["generation_config_hash"] == "ghash1"
        assert meta["operators"][0]["operator"] in ("displace", "substitute")
        assert meta["novelty_tag"] in ("novel", "rediscovery")
        assert "p0_passed" in meta and len(kid.evidence_log) == 1


def test_near_zero_perturbation_tags_rediscovery():
    """Near-zero displacement must match the parent (rediscovery, not novel)."""
    kids = generate_children(
        _parent(), operators=["displace"], children_per_parent=2, seed=0,
        displacement_sigma_A_provisional=1e-6,
    )
    assert len(kids) == 2
    for kid in kids:
        assert kid.metadata["novelty_tag"] == "rediscovery"
        assert kid.metadata["novelty_matched"] == "parent"


def _li2o():
    """3-site fixture where Li vacancy breaks neutrality (Li2O -> LiO)."""
    lattice = Lattice.cubic(4.6)
    return Structure(lattice, ["Li", "Li", "O"],
                     [[0.0, 0.0, 0.0], [0.5, 0.5, 0.0], [0.5, 0.0, 0.5]])


def test_vacancy_child_tags_novel_and_runs_p0_at_birth():
    """A composition-changing child is novel and always carries a P0 verdict."""
    kids = generate_children(
        _parent(_li2o()), operators=["vacancy"], children_per_parent=1, seed=0)
    assert len(kids) == 1
    kid = kids[0]
    assert kid.metadata["novelty_tag"] == "novel"
    assert kid.metadata["p0_passed"] is False  # Li2O minus Li -> LiO: not neutral
    assert kid.existence_state == ExistenceState.FAIL
    assert "p0_rejection" in kid.metadata  # FAIL kept with reason, not dropped
    assert len(kid.evidence_log) == 1 and kid.evidence_log[0].level == "P0"


def test_calibrated_matcher_tolerances():
    """Pin the 2026-09 calibration: duplicates match, distinct pairs don't.

    Uses the config matcher values explicitly. True duplicates (identity,
    numerical noise) must match; cross-material and 10x-magnitude pairs
    must not. If this fails after a tolerance change, recalibrate first.
    """
    import yaml
    from pymatgen.analysis.structure_matcher import StructureMatcher

    with open("config.yaml", encoding="utf-8") as f:
        m_cfg = yaml.safe_load(f)["generation"]["matcher"]
    matcher = StructureMatcher(
        ltol=m_cfg["ltol_provisional"],
        stol=m_cfg["stol_provisional"],
        angle_tol=m_cfg["angle_tol_provisional"],
    )
    base = _licl()
    rng = np.random.default_rng(3)
    noise, _ = op_displace(base, rng, 1e-6)
    other = Structure(Lattice.cubic(5.6), ["Na", "Br"],
                      [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]])
    # NOTE: pure displacement still matches on a 2-atom toy even at 10x sigma
    # (2 sites always re-align within stol); lattice destruction is the
    # honest distinct-by-construction case here. Real-cell evidence for the
    # displacement boundary lives in the calibration note in config.yaml.
    wild, _ = op_strain(base, rng, 0.10)

    assert matcher.fit(base, base.copy())
    assert matcher.fit(base, noise)
    assert not matcher.fit(base, other)
    assert not matcher.fit(base, wild)


def test_liion_structureless_parent_not_perturbable(tmp_path):
    """LiIon rows without a matchable structure are retrievable, not perturbable."""
    if not Path("data/obelix").exists():
        pytest.skip("data/obelix repository not found locally")
    csv = tmp_path / "li.csv"
    csv.write_text(
        "ID,composition,source,temperature,target,log_target,family,ChemicalFamily\n"
        "1,UnobtaniumX2,doi:10.1/x,25.0,1e-4,-4.0,x,Oxides\n"
    )
    parents = retrieve_liion_parents(str(csv), "data/obelix")
    assert len(parents) == 1
    assert parents[0].structure is None
    assert parents[0].perturbable is False
    assert generate_children(parents[0], ["displace"], 2, seed=0) == []


def test_obelix_parent_retrieval_provenance():
    """OBELiX parents carry dataset + ID + sha256 provenance."""
    if not Path("data/obelix").exists():
        pytest.skip("data/obelix repository not found locally")
    parents = retrieve_obelix_parents("data/obelix")
    assert len(parents) > 300  # all CIF-linked entries, train AND test
    for p in parents[:5]:
        assert p.parent_id.startswith("obelix:")
        assert p.source_dataset == "obelix"
        assert len(p.structure_sha256) == 64
        assert "structure_sha256" in p.provenance

from rudeus.generation.scheduler import (
    GenerationAuditRow,
    GenerationScheduleRecord,
    ScheduleState,
)


def test_generation_schedule_record_serializes_enum_value():
    record = GenerationScheduleRecord(
        parent_id="obelix:test",
        parent_chemical_family="oxide",
        operator_name="displace",
        operator_version="legacy-v1",
        schedule_state=ScheduleState.SCHEDULED,
        reason="baseline",
        seed=42,
        generation_config_hash="abc123",
        child_material_id="g1-deadbeef",
    )

    data = record.to_dict()

    assert data["parent_id"] == "obelix:test"
    assert data["operator_name"] == "displace"
    assert data["operator_version"] == "legacy-v1"
    assert data["schedule_state"] == "SCHEDULED"
    assert data["child_material_id"] == "g1-deadbeef"


def test_generation_schedule_record_can_represent_no_child():
    record = GenerationScheduleRecord(
        parent_id="obelix:test",
        parent_chemical_family="oxide",
        operator_name="vacancy",
        operator_version="legacy-v1",
        schedule_state=ScheduleState.DISABLED_BY_POLICY,
        reason="legacy uncompensated defect disabled in candidate-supply-v2",
        seed=42,
        generation_config_hash="abc123",
    )

    data = record.to_dict()

    assert data["schedule_state"] == "DISABLED_BY_POLICY"
    assert data["child_material_id"] is None


def test_generation_audit_row_serializes_lossless_pre_p1_fields():
    row = GenerationAuditRow(
        parent_id="obelix:test",
        parent_chemical_family="oxide",
        operator_name="substitute",
        operator_version="legacy-v1",
        schedule_state=ScheduleState.SCHEDULED,
        child_material_id="g1-cafebabe",
        child_index=0,
        seed=42,
        generation_config_hash="abc123",
        operator_error=None,
        p0_state="PLAUSIBLE",
        p0_neutrality_ok=True,
        p0_pauling_ok=True,
        p0_geometry_ok=True,
        p0_rejection_class=None,
        novelty_tag="novel",
        novelty_matched=None,
        p1_eligible=True,
    )

    data = row.to_dict()

    assert data["schedule_state"] == "SCHEDULED"
    assert data["p0_state"] == "PLAUSIBLE"
    assert data["p0_neutrality_ok"] is True
    assert data["novelty_tag"] == "novel"
    assert data["p1_eligible"] is True

def test_candidate_supply_v2_schedule_is_explicit_and_deterministic():
    from rudeus.generation.scheduler import schedule_candidate_supply_v2

    a = schedule_candidate_supply_v2(
        parent_id="obelix:test",
        parent_chemical_family="oxide",
        seed=42,
        generation_config_hash="abc123",
    )
    b = schedule_candidate_supply_v2(
        parent_id="obelix:test",
        parent_chemical_family="oxide",
        seed=42,
        generation_config_hash="abc123",
    )

    assert [r.to_dict() for r in a] == [r.to_dict() for r in b]

    by_op = {r.operator_name: r for r in a}

    assert set(by_op) == {
        "displace",
        "strain",
        "vacancy",
        "interstitial",
        "substitute",
    }

    assert by_op["displace"].schedule_state == ScheduleState.SCHEDULED
    assert by_op["strain"].schedule_state == ScheduleState.DEFERRED_PENDING_DESIGN
    assert by_op["vacancy"].schedule_state == ScheduleState.DISABLED_BY_POLICY
    assert by_op["interstitial"].schedule_state == ScheduleState.DISABLED_BY_POLICY
    assert by_op["substitute"].schedule_state == ScheduleState.DEFERRED_PENDING_DESIGN


def test_candidate_supply_v2_schedule_uses_versioned_operator_semantics():
    from rudeus.generation.scheduler import schedule_candidate_supply_v2

    records = schedule_candidate_supply_v2(
        parent_id="obelix:test",
        parent_chemical_family="sulfide",
        seed=99,
        generation_config_hash="ghash",
    )

    by_op = {r.operator_name: r for r in records}

    assert by_op["displace"].operator_version == "legacy-v1"
    assert by_op["strain"].operator_version == "legacy-v1"
    assert by_op["vacancy"].operator_version == "legacy-v1"
    assert by_op["interstitial"].operator_version == "legacy-v1"

    # Legacy substitute is not activated as v2 supply until the
    # neutrality-aware substitution design is implemented.
    assert by_op["substitute"].operator_version == "legacy-v1"

    assert all(r.child_material_id is None for r in records)

def test_generation_audit_row_from_candidate_preserves_pre_p1_evidence():
    from rudeus.generation.scheduler import audit_row_from_candidate

    kids = generate_children(
        _parent(),
        operators=["displace"],
        children_per_parent=1,
        seed=17,
        generation_config_hash="ghash-v2-test",
        displacement_sigma_A_provisional=0.05,
    )
    assert len(kids) == 1

    kid = kids[0]

    row = audit_row_from_candidate(
        candidate=kid,
        parent_chemical_family="halide",
        operator_version="legacy-v1",
        schedule_state=ScheduleState.SCHEDULED,
        p1_eligible=True,
    )

    data = row.to_dict()

    assert data["parent_id"] == "test:licl"
    assert data["parent_chemical_family"] == "halide"
    assert data["operator_name"] == "displace"
    assert data["operator_version"] == "legacy-v1"
    assert data["schedule_state"] == "SCHEDULED"
    assert data["child_material_id"] == kid.material_id
    assert data["child_index"] == 0
    assert data["seed"] == 17
    assert data["generation_config_hash"] == "ghash-v2-test"

    assert data["p0_state"] == kid.existence_state.value
    assert data["p0_neutrality_ok"] == kid.metadata["p0_details"]["neutrality_ok"]
    assert data["p0_pauling_ok"] == kid.metadata["p0_details"]["pauling_ok"]
    assert data["p0_geometry_ok"] == kid.metadata["p0_details"]["geometry_ok"]

    assert data["novelty_tag"] == kid.metadata["novelty_tag"]
    assert data["novelty_matched"] == kid.metadata["novelty_matched"]
    assert data["p1_eligible"] is True


def test_generation_audit_row_from_candidate_classifies_p0_rejection():
    from rudeus.generation.scheduler import audit_row_from_candidate

    kids = generate_children(
        _parent(_li2o()),
        operators=["vacancy"],
        children_per_parent=1,
        seed=0,
        generation_config_hash="ghash-v2-test",
    )
    assert len(kids) == 1

    kid = kids[0]

    row = audit_row_from_candidate(
        candidate=kid,
        parent_chemical_family="oxide",
        operator_version="legacy-v1",
        schedule_state=ScheduleState.SCHEDULED,
        p1_eligible=False,
    )

    data = row.to_dict()

    assert data["operator_name"] == "vacancy"
    assert data["p0_state"] == "FAIL"
    assert data["p0_neutrality_ok"] is False
    assert data["p0_rejection_class"] == "neutrality"
    assert data["p1_eligible"] is False

def test_candidate_supply_v2_audit_payload_is_lossless_and_json_ready():
    from rudeus.generation.scheduler import build_candidate_supply_v2_audit

    schedule_records = [
        GenerationScheduleRecord(
            parent_id="obelix:test",
            parent_chemical_family="oxide",
            operator_name="displace",
            operator_version="legacy-v1",
            schedule_state=ScheduleState.SCHEDULED,
            reason="baseline",
            seed=42,
            generation_config_hash="ghash",
            child_material_id="g1-child",
        ),
        GenerationScheduleRecord(
            parent_id="obelix:test",
            parent_chemical_family="oxide",
            operator_name="vacancy",
            operator_version="legacy-v1",
            schedule_state=ScheduleState.DISABLED_BY_POLICY,
            reason="disabled",
            seed=42,
            generation_config_hash="ghash",
            child_material_id=None,
        ),
    ]

    child_rows = [
        GenerationAuditRow(
            parent_id="obelix:test",
            parent_chemical_family="oxide",
            operator_name="displace",
            operator_version="legacy-v1",
            schedule_state=ScheduleState.SCHEDULED,
            child_material_id="g1-child",
            child_index=0,
            seed=42,
            generation_config_hash="ghash",
            operator_error=None,
            p0_state="PLAUSIBLE",
            p0_neutrality_ok=True,
            p0_pauling_ok=True,
            p0_geometry_ok=True,
            p0_rejection_class=None,
            novelty_tag="novel",
            novelty_matched=None,
            p1_eligible=True,
        )
    ]

    payload = build_candidate_supply_v2_audit(
        schedule_records=schedule_records,
        child_rows=child_rows,
    )

    assert payload["audit_version"] == "candidate-supply-v2-audit-v1"
    assert len(payload["schedule_records"]) == 2
    assert len(payload["child_rows"]) == 1

    assert payload["schedule_records"][0]["schedule_state"] == "SCHEDULED"
    assert payload["schedule_records"][1]["child_material_id"] is None
    assert payload["child_rows"][0]["p1_eligible"] is True

    # Aggregates are derived convenience fields, not replacements for raw rows.
    assert payload["summary"]["schedule_records"] == 2
    assert payload["summary"]["children_generated"] == 1
    assert payload["summary"]["p1_eligible"] == 1


def test_write_candidate_supply_v2_audit_creates_nested_json_without_temp_files(
    tmp_path,
):
    from rudeus.generation.scheduler import write_candidate_supply_v2_audit

    payload = {
        "audit_version": "candidate-supply-v2-audit-v1",
        "child_rows": [{"p1_eligible": True, "nested": {"value": "한국어"}}],
        "summary": {"children_generated": 1},
    }
    path = tmp_path / "nested" / "audit" / "payload.json"

    write_candidate_supply_v2_audit(path, payload)

    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert list(path.parent.glob(f".{path.name}.*.tmp")) == []


def test_execute_candidate_supply_v2_for_parent_runs_only_scheduled_displace():
    from rudeus.generation.scheduler import (
        execute_candidate_supply_v2_for_parent,
    )

    kwargs = {
        "seed": 17,
        "generation_config_hash": "ghash-v2-test",
        "displacement_sigma_A_provisional": 0.05,
    }
    schedule_records, audit_rows, children = (
        execute_candidate_supply_v2_for_parent(_parent(), **kwargs)
    )
    repeat_records, repeat_rows, repeat_children = (
        execute_candidate_supply_v2_for_parent(_parent(), **kwargs)
    )

    assert len(schedule_records) == 5
    assert len(children) == 1
    child = children[0]
    assert child.metadata["operators"][0]["operator"] == "displace"
    assert len(audit_rows) == 1

    scheduled = [
        record for record in schedule_records
        if record.schedule_state is ScheduleState.SCHEDULED
    ]
    assert len(scheduled) == 1
    assert scheduled[0].child_material_id == child.material_id
    assert all(
        record.child_material_id is None
        for record in schedule_records
        if record.schedule_state is not ScheduleState.SCHEDULED
    )

    audit_row = audit_rows[0]
    assert audit_row.child_material_id == child.material_id
    assert audit_row.operator_name == "displace"
    assert audit_row.parent_id == _parent().parent_id

    assert [record.to_dict() for record in schedule_records] == [
        record.to_dict() for record in repeat_records
    ]
    assert [row.to_dict() for row in audit_rows] == [
        row.to_dict() for row in repeat_rows
    ]
    repeat_child = repeat_children[0]
    assert child.material_id == repeat_child.material_id
    assert child.formula == repeat_child.formula
    assert child.structure_dict == repeat_child.structure_dict
    assert child.existence_state == repeat_child.existence_state
    assert child.dynamic_state == repeat_child.dynamic_state
    assert child.transport_state == repeat_child.transport_state
    assert child.metadata == repeat_child.metadata
    assert len(child.evidence_log) == len(repeat_child.evidence_log)
    assert [
        {
            key: value
            for key, value in event.to_dict().items()
            if key != "timestamp"
        }
        for event in child.evidence_log
    ] == [
        {
            key: value
            for key, value in event.to_dict().items()
            if key != "timestamp"
        }
        for event in repeat_child.evidence_log
    ]


def test_execute_candidate_supply_v2_cohort_preserves_order_seeds_and_audit():
    from dataclasses import replace

    from rudeus.generation.scheduler import (
        execute_candidate_supply_v2_cohort,
    )

    parents = [
        replace(_parent(), parent_id="test:first"),
        replace(_parent(), parent_id="test:second"),
    ]
    kwargs = {
        "base_seed": 31,
        "generation_config_hash": "ghash-v2-cohort-test",
    }

    records, rows, children, payload = execute_candidate_supply_v2_cohort(
        parents, **kwargs
    )
    repeat_records, repeat_rows, repeat_children, repeat_payload = (
        execute_candidate_supply_v2_cohort(parents, **kwargs)
    )

    assert len(records) == 10
    assert len(children) == 2
    assert [record.parent_id for record in records[::5]] == [
        "test:first",
        "test:second",
    ]
    assert [record.seed for record in records[::5]] == [31, 32]
    assert [child.metadata["parent_id"] for child in children] == [
        "test:first",
        "test:second",
    ]
    assert all(
        child.metadata["operators"][0]["operator"] == "displace"
        for child in children
    )
    assert len(rows) == 2
    assert [row.child_material_id for row in rows] == [
        child.material_id for child in children
    ]
    assert payload["schedule_records"] == [record.to_dict() for record in records]
    assert payload["child_rows"] == [row.to_dict() for row in rows]
    assert payload["summary"]["schedule_records"] == 10
    assert payload["summary"]["children_generated"] == 2

    assert [record.to_dict() for record in records] == [
        record.to_dict() for record in repeat_records
    ]
    assert [row.to_dict() for row in rows] == [
        row.to_dict() for row in repeat_rows
    ]
    assert repeat_payload == payload
    for child, repeat_child in zip(children, repeat_children):
        assert child.material_id == repeat_child.material_id
        assert child.formula == repeat_child.formula
        assert child.structure_dict == repeat_child.structure_dict
        assert child.existence_state == repeat_child.existence_state
        assert child.metadata == repeat_child.metadata
        assert len(child.evidence_log) == len(repeat_child.evidence_log)


def test_execute_candidate_supply_v2_cohort_represents_nonperturbable_parent():
    from dataclasses import replace

    from rudeus.generation.scheduler import (
        execute_candidate_supply_v2_cohort,
    )

    parent = replace(_parent(), parent_id="test:nonperturbable", perturbable=False)
    records, rows, children, payload = execute_candidate_supply_v2_cohort(
        [parent],
        base_seed=41,
        generation_config_hash="ghash-v2-cohort-test",
    )

    assert len(records) == 5
    assert rows == []
    assert children == []
    displace = next(record for record in records if record.operator_name == "displace")
    assert displace.schedule_state is ScheduleState.INAPPLICABLE
    assert "not perturbable" in displace.reason
    assert displace.child_material_id is None
    assert payload["schedule_records"] == [record.to_dict() for record in records]
    assert payload["child_rows"] == []


def test_candidate_supply_v2_blocks_parent_p0_neutrality_failure_before_displace():
    from dataclasses import replace

    from rudeus.generation.scheduler import (
        execute_candidate_supply_v2_for_parent,
    )

    invalid_structure = Structure(
        Lattice.cubic(4.6),
        ["Li", "O"],
        [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
    )
    parent = replace(
        _parent(invalid_structure),
        parent_id="obelix:d7f",
        composition="LiO",
        chemical_family="oxide",
    )
    parent_p0 = evaluate_p0(parent.composition, structure=parent.structure)
    assert parent_p0.neutrality_ok is False
    assert parent_p0.pauling_ok is True
    assert parent_p0.geometry_ok is True

    records, audit_rows, children = execute_candidate_supply_v2_for_parent(
        parent,
        seed=42,
        generation_config_hash="ghash-v2-test",
    )

    assert len(records) == 5
    assert children == []
    assert audit_rows == []
    displace = next(record for record in records if record.operator_name == "displace")
    assert displace.child_material_id is None
    assert displace.schedule_state.value == "BLOCKED_BY_PARENT_P0"
    assert "parent P0 neutrality" in displace.reason


def test_candidate_supply_v2_plausible_parent_still_displaces_and_cohort_summary_is_raw_derived():
    from dataclasses import replace

    from rudeus.generation.scheduler import (
        execute_candidate_supply_v2_cohort,
        execute_candidate_supply_v2_for_parent,
    )

    plausible = _parent()
    records, audit_rows, children = execute_candidate_supply_v2_for_parent(
        plausible,
        seed=42,
        generation_config_hash="ghash-v2-test",
    )
    assert len(records) == 5
    assert len(children) == 1
    assert len(audit_rows) == 1
    assert children[0].metadata["operators"][0]["operator"] == "displace"

    invalid_structure = Structure(
        Lattice.cubic(4.6),
        ["Li", "O"],
        [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
    )
    blocked = replace(
        _parent(invalid_structure),
        parent_id="obelix:d7f",
        composition="LiO",
        chemical_family="oxide",
    )
    schedule_records, child_rows, cohort_children, payload = (
        execute_candidate_supply_v2_cohort(
            [blocked, plausible],
            base_seed=42,
            generation_config_hash="ghash-v2-test",
        )
    )
    assert len(schedule_records) == 10
    assert len(child_rows) == len(cohort_children) == 1
    assert payload["summary"]["schedule_records"] == len(schedule_records)
    assert payload["summary"]["children_generated"] == len(cohort_children)
    assert payload["summary"]["p1_eligible"] == sum(
        row.p1_eligible for row in child_rows
    )
