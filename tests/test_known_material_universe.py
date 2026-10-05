"""B2 literature-grounded universe intake tests."""
import json
from pathlib import Path

from rudeus.science.known_material_benchmark import TruthClass, build_known_material_benchmark_protocol
from rudeus.science.known_material_truth import TRUTH_RECORD_VERSION
from rudeus.science.known_material_universe import (
    CurationState,
    MaterialUniverseIntake,
    UNIVERSE_VERSION,
)


DATA = Path("data/benchmarks/known_material/b2_universe_intake_v1.json")


def load():
    return MaterialUniverseIntake.from_dict(json.loads(DATA.read_text(encoding="utf-8")))


def test_b2_intake_binds_exact_b0_and_b1_contract_versions():
    universe = load()
    assert universe.universe_version == UNIVERSE_VERSION
    assert universe.truth_record_version == TRUTH_RECORD_VERSION
    assert universe.benchmark_protocol_hash == build_known_material_benchmark_protocol().content_hash


def test_b2_has_positive_negative_and_condition_sensitive_controls():
    universe = load()
    roles = {entry.proposed_role for entry in universe.entries}
    assert TruthClass.POSITIVE.value in roles
    assert TruthClass.NEGATIVE.value in roles
    assert TruthClass.BORDERLINE.value in roles
    assert len({entry.chemistry_family for entry in universe.entries}) >= 4


def test_b2_does_not_assign_blinded_split_or_benchmark_ids():
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    for entry in raw["entries"]:
        assert "split" not in entry
        assert "benchmark_id" not in entry
        assert "expected_stage_outcomes" not in entry
    universe = load()
    assert not universe.dev_held_out_assignment_authorized


def test_b2_does_not_authorize_thresholds_execution_or_production():
    universe = load()
    assert not universe.numeric_qualification_thresholds_authorized
    assert not universe.pipeline_execution_authorized
    assert not universe.production_search_authorized


def test_every_entry_is_source_grounded_but_not_prematurely_truth_bundle_ready():
    universe = load()
    assert all(entry.literature_sources for entry in universe.entries)
    assert all(entry.blockers for entry in universe.entries)
    assert all(entry.curation_state != CurationState.TRUTH_BUNDLE_READY.value
               for entry in universe.entries)


def test_transport_semantics_keep_conductivity_separate_from_self_diffusion():
    universe = load()
    lgps = next(entry for entry in universe.entries
                if entry.material_key == "lgps-tetragonal-li10gep2s12")
    li2s = next(entry for entry in universe.entries
                if entry.material_key == "li2s-microcrystalline")
    assert "self_diffusion_specific_truth_required_for_P2.5" in lgps.blockers
    assert "self_diffusion_specific_negative_truth_required_for_P2.5_scoring" in li2s.blockers


def test_phase_and_representation_risks_are_not_collapsed():
    universe = load()
    keys = {entry.material_key: entry for entry in universe.entries}
    assert keys["llzo-cubic-al-stabilized"].phase_context != keys["llzo-tetragonal-undoped"].phase_context
    assert any("surface_porosity" in blocker for blocker in keys["li3ps4-nanoporous-beta"].blockers)
    assert any("disorder" in blocker for blocker in keys["li6ps5cl-argyrodite"].blockers)
