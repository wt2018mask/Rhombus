"""B4 execution-structure hash semantics tests."""
from dataclasses import replace

import pytest

from rudeus.science.known_material_b4_execution_structure import (
    EXECUTION_STRUCTURE_BINDING_VERSION,
    ExecutionStructureBinding,
    ExecutionStructureComponent,
)


def component(label, digest, *, n=None, d=None):
    return ExecutionStructureComponent(
        label=label,
        structure_hash=digest,
        weight_numerator=n,
        weight_denominator=d,
    )


def test_direct_visible_hash_remains_raw_structure_hash():
    raw = "1" * 64
    binding = ExecutionStructureBinding(
        binding_version=EXECUTION_STRUCTURE_BINDING_VERSION,
        mode="DIRECT",
        components=(component("structure", raw),),
    )
    assert binding.visible_structure_hash == raw


def test_phase_set_visible_hash_binds_all_phase_components():
    binding = ExecutionStructureBinding(
        binding_version=EXECUTION_STRUCTURE_BINDING_VERSION,
        mode="PHASE_SET",
        components=(
            component("hexagonal", "2" * 64),
            component("orthorhombic", "3" * 64),
        ),
    )
    assert len(binding.visible_structure_hash) == 64
    assert binding.visible_structure_hash not in {"2" * 64, "3" * 64}


def test_weighted_ensemble_visible_hash_binds_weights_and_assumption():
    binding = ExecutionStructureBinding(
        binding_version=EXECUTION_STRUCTURE_BINDING_VERSION,
        mode="ENSEMBLE",
        components=(
            component("member-00", "4" * 64, n=1, d=4),
            component("member-01", "5" * 64, n=3, d=4),
        ),
        weighting_assumption="source-derived-test-weights",
    )
    changed = replace(
        binding,
        weighting_assumption="different-assumption",
    )
    assert binding.visible_structure_hash != changed.visible_structure_hash


def test_ensemble_rejects_non_normalized_weights():
    with pytest.raises(ValueError, match="sum exactly to one"):
        ExecutionStructureBinding(
            binding_version=EXECUTION_STRUCTURE_BINDING_VERSION,
            mode="ENSEMBLE",
            components=(
                component("member-00", "4" * 64, n=1, d=4),
                component("member-01", "5" * 64, n=1, d=4),
            ),
            weighting_assumption="test",
        )


def test_component_order_is_canonical():
    with pytest.raises(ValueError, match="sorted by label"):
        ExecutionStructureBinding(
            binding_version=EXECUTION_STRUCTURE_BINDING_VERSION,
            mode="PHASE_SET",
            components=(
                component("orthorhombic", "3" * 64),
                component("hexagonal", "2" * 64),
            ),
        )
