"""Design contract for paired baseline/clearance mobile-ion diagnostics."""

import json
from types import SimpleNamespace

import numpy as np
from pymatgen.core import Lattice, Structure

from rudeus.filters.p0 import check_geometry_clash
from rudeus.generation.generator import ParentRecord


def _parent(parent_id, coords, family="synthetic-oxide"):
    structure = Structure(Lattice.cubic(20.0), ["Na", "Na", "O"], coords)
    return ParentRecord(
        parent_id=parent_id,
        source_dataset="fixture",
        source_ref=parent_id,
        composition=str(structure.composition.reduced_formula),
        structure=structure,
        structure_sha256="synthetic-fixture",
        conductivity=None,
        chemical_family=family,
        perturbable=True,
        provenance={"source": "paired-clearance-design-fixture"},
    )


class _ProposalStream:
    def __init__(self, vectors):
        self.vectors = list(vectors)

    def normal(self, loc, scale, size):
        assert loc == 0.0
        assert size == 3
        return np.asarray(self.vectors.pop(0), dtype=float)


def _install_streams(monkeypatch, diagnostic, vectors_by_rng):
    streams = iter(vectors_by_rng)
    monkeypatch.setattr(
        diagnostic.np.random,
        "default_rng",
        lambda _seed: _ProposalStream(next(streams)),
    )


def _run_panel(parents, *, monkeypatch, vectors_by_rng, sigmas=(0.2,), seeds=(17,), max_attempts=2):
    # The paired builder is intentionally not implemented yet; these tests
    # define its smallest useful observational API.
    from rudeus.generation import mobile_ion_diagnostic as diagnostic

    _install_streams(monkeypatch, diagnostic, vectors_by_rng)
    return diagnostic.build_mobile_ion_clearance_paired_diagnostic_panel(
        parents,
        mobile_ion="Na",
        sigma_values_A_provisional=list(sigmas),
        base_seeds=list(seeds),
        diagnostic_config_hash="paired-fixture-config-v1",
        max_attempts=max_attempts,
    )


def _passing_p0_from_existing_clash_rule(_formula, *, structure):
    geometry_ok, details = check_geometry_clash(structure)
    plausible = geometry_ok is True
    return SimpleNamespace(
        neutrality_ok=True,
        pauling_ok=True,
        geometry_ok=geometry_ok,
        existence_state=SimpleNamespace(
            value="PLAUSIBLE" if plausible else "FAIL"
        ),
        details={"geometry": details},
    )


def _fixture_streams():
    zero = [0.0, 0.0, 0.0]
    separate = [0.0, 0.0, 2.0]
    # Each pair gets independent baseline and clearance RNGs initialized from
    # the same proposal stream. Na has two sites, so each attempt draws twice.
    return [
        [zero, zero], [zero, zero],                         # clear / clear
        [zero, zero], [zero, zero, separate, zero],        # clash / retry-pass
        [zero, zero], [zero, zero, zero, zero],            # clash / exhaustion
    ]


def test_paired_clearance_panel_reconciles_transitions_and_excludes_exhaustion_from_material_evidence(monkeypatch):
    from rudeus.generation import mobile_ion_diagnostic as diagnostic

    monkeypatch.setattr(diagnostic, "evaluate_p0", _passing_p0_from_existing_clash_rule)
    monkeypatch.setattr(
        diagnostic,
        "classify_candidate_supply_v2_novelty",
        lambda *_args, **_kwargs: {
            "novelty_tag": "novel",
            "novelty_matched": None,
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
        },
    )
    parents = [
        _parent(
            "fixture:clear",
            [[0.10, 0.10, 0.10], [0.60, 0.60, 0.60], [0.10, 0.60, 0.60]],
            "oxide-clear",
        ),
        _parent(
            "fixture:retry",
            [[0.10, 0.10, 0.10], [0.60, 0.60, 0.60], [0.15, 0.10, 0.10]],
            "oxide-retry",
        ),
        _parent(
            "fixture:exhaust",
            [[0.10, 0.10, 0.10], [0.60, 0.60, 0.60], [0.15, 0.10, 0.10]],
            "oxide-exhaust",
        ),
    ]
    parent_before = [parent.structure.as_dict() for parent in parents]
    panel = _run_panel(
        parents, monkeypatch=monkeypatch, vectors_by_rng=_fixture_streams()
    )

    assert panel["schema_version"] == "mobile-ion-clearance-paired-diagnostic-v1"
    assert panel["artifact_type"] == "OBSERVATIONAL_DIAGNOSTIC"
    assert panel["authorization"] == {
        "scheduler_activation": False,
        "p1_eligibility": False,
        "downstream_scientific_claims": False,
        "operator_superiority": False,
        "automatic_parent_exclusion": False,
        "chemistry_exclusion": False,
        "threshold_modification": False,
    }
    assert [row["parent_id"] for row in panel["rows"]] == [
        parent.parent_id for parent in parents
    ]
    assert all(row["target_species"] == "Na" for row in panel["rows"])
    assert all(row["chemical_family"] == parent.chemical_family
               for row, parent in zip(panel["rows"], parents))
    assert [parent.structure.as_dict() for parent in parents] == parent_before

    clear, retry, exhaust = panel["rows"]
    for row in panel["rows"]:
        assert row["pair_id"]
        assert row["sigma_A_provisional"] == 0.2
        assert row["base_seed"] == 17
        assert row["pair_rng_identity"]
        assert isinstance(row["pair_rng_seed"], int)
        assert row["baseline"]["operator_name"] == "mobile-ion-displace"
        assert row["baseline"]["operator_version"] == "mobile-ion-displace-v2"
        assert row["clearance"]["operator_name"] == "mobile-ion-displace-clearance"
        assert row["clearance"]["operator_version"] == "mobile-ion-displace-clearance-v1"
        assert row["baseline"]["operator_rng_identity"] == row["pair_rng_identity"]
        assert row["clearance"]["operator_rng_identity"] == row["pair_rng_identity"]
        assert row["baseline"]["operator_rng_seed"] == row["pair_rng_seed"]
        assert row["clearance"]["operator_rng_seed"] == row["pair_rng_seed"]
        assert row["baseline"]["generated"] is True

    assert clear["baseline"]["child_structure_dict"] == clear["clearance"]["child_structure_dict"]
    assert clear["clearance"]["proposal_status"] == "ACCEPTED"
    assert clear["clearance"]["attempts_used"] == 1
    assert clear["baseline"]["p0_plausible"] is True
    assert clear["baseline"]["p0_geometry_ok"] is True
    assert clear["baseline"]["novelty_tag"] == "novel"
    assert clear["baseline"]["novelty_matcher_version"] == "novelty-matcher-v2-same-cell"
    assert clear["clearance"]["p0_plausible"] is True
    assert clear["clearance"]["novelty_tag"] == "novel"
    assert clear["transitions"]["geometry"] == "PASS_TO_PASS"

    assert retry["baseline"]["p0_geometry_ok"] is False
    assert retry["baseline"]["geometry_clash_evidence"]["clash_detected"] is True
    assert retry["clearance"]["proposal_status"] == "ACCEPTED"
    assert retry["clearance"]["attempts_used"] == 2
    assert retry["clearance"]["rejected_clash_attempts"] == 1
    assert retry["clearance"]["p0_geometry_ok"] is True
    assert retry["transitions"]["geometry"] == "FAIL_TO_PASS"

    assert exhaust["baseline"]["p0_geometry_ok"] is False
    assert exhaust["clearance"]["proposal_status"] == "EXHAUSTED"
    assert exhaust["clearance"]["attempts_used"] == 2
    assert exhaust["clearance"]["generated"] is False
    assert exhaust["clearance"]["novelty_tag"] is None
    assert exhaust["clearance"]["p0_state"] is None
    assert exhaust["clearance"]["p0_geometry_ok"] is None
    assert exhaust["clearance"]["useful"] is None
    assert exhaust["transitions"]["geometry"] == "FAIL_TO_EXHAUSTED"
    assert exhaust["transitions"]["useful"] == "FALSE_TO_NOT_EVALUATED"

    summary = panel["summary"]
    assert summary["requested_pairs"] == 3
    assert summary["baseline_generated"] == 3
    assert summary["clearance_accepted"] == 2
    assert summary["clearance_exhausted"] == 1
    assert summary["clearance_accepted"] + summary["clearance_exhausted"] == summary["requested_pairs"]
    assert summary["paired_generated_both"] == summary["clearance_accepted"] == 2
    assert summary["baseline_geometry_fail_rows"] == 2
    assert summary["clearance_geometry_fail_rows"] == 0
    assert summary["baseline_novel_rows"] == 3
    assert summary["clearance_novel_rows"] == 2
    assert summary["baseline_useful_rows"] == 1
    assert summary["clearance_useful_rows"] == 2
    assert sum(summary["geometry_transition_counts"].values()) == 3
    assert sum(summary["useful_transition_counts"].values()) == 3
    assert summary["attempts_used_distribution"] == {"1": 1, "2": 2}
    assert summary["rejected_clash_attempts_distribution"] == {"0": 1, "1": 1, "2": 1}
    assert summary["max_attempts_used"] == 2
    assert summary["exhaustion_rate"] == 1 / 3
    assert summary["paired_common_subset"]["denominator"] == 2
    assert summary["paired_common_subset"]["baseline_geometry_fail_fraction"] == 0.5
    assert summary["paired_common_subset"]["clearance_geometry_fail_fraction"] == 0.0
    assert summary["paired_common_subset"]["baseline_novel_denominator"] == 2
    assert summary["paired_common_subset"]["clearance_novel_denominator"] == 2
    assert summary["paired_common_subset"]["baseline_useful_denominator"] == 2
    assert summary["paired_common_subset"]["clearance_useful_denominator"] == 2
    assert summary["overall_clearance_yield"]["accepted_over_requested"] == 2 / 3
    assert summary["overall_clearance_yield"]["exhausted_over_requested"] == 1 / 3
    assert summary["overall_clearance_yield"]["useful_accepted_over_requested"] == 2 / 3
    assert summary["overall_clearance_yield"]["novel_accepted_over_requested"] == 2 / 3
    assert not {"winner", "superior_operator", "recommended_operator", "promotion_decision"}.intersection(panel)


def test_paired_clearance_panel_preserves_sigma_seed_cartesian_product_and_is_deterministic(monkeypatch):
    from rudeus.generation import mobile_ion_diagnostic as diagnostic

    monkeypatch.setattr(diagnostic, "evaluate_p0", _passing_p0_from_existing_clash_rule)
    monkeypatch.setattr(
        diagnostic,
        "classify_candidate_supply_v2_novelty",
        lambda *_args, **_kwargs: {
            "novelty_tag": "rediscovery",
            "novelty_matched": "parent",
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
        },
    )
    parent = _parent(
        "fixture:cartesian-product",
        [[0.10, 0.10, 0.10], [0.60, 0.60, 0.60], [0.10, 0.60, 0.60]],
    )

    def fresh_streams():
        return [[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]] for _ in range(8)]

    kwargs = dict(
        mobile_ion="Na",
        sigma_values_A_provisional=[0.1, 0.2],
        base_seeds=[41, 42],
        diagnostic_config_hash="paired-fixture-config-v1",
        max_attempts=2,
    )
    outputs = []
    for _ in range(2):
        _install_streams(monkeypatch, diagnostic, fresh_streams())
        outputs.append(
            diagnostic.build_mobile_ion_clearance_paired_diagnostic_panel(
                [parent], **kwargs
            )
        )

    assert [(row["parent_id"], row["sigma_A_provisional"], row["base_seed"])
            for row in outputs[0]["rows"]] == [
        (parent.parent_id, sigma, seed)
        for sigma in kwargs["sigma_values_A_provisional"]
        for seed in kwargs["base_seeds"]
    ]
    assert json.dumps(outputs[0], sort_keys=True, separators=(",", ":")) == json.dumps(
        outputs[1], sort_keys=True, separators=(",", ":")
    )
    assert outputs[0]["summary"]["requested_pairs"] == 4
