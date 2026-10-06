"""B4 blind-ingress contract tests."""
from dataclasses import fields

import pytest

from rudeus.science.known_material_b4_ingress import (
    BlindBenchmarkIngress,
    VISIBLE_FIELDS,
)


HASH = "1" * 64


def test_execution_payload_contains_only_b0_visible_fields():
    ingress = BlindBenchmarkIngress(
        ingress_version="known-material-blind-ingress-v1",
        benchmark_id="km-001",
        split="DEV",
        structure_hash=HASH,
        benchmark_protocol_hash="2" * 64,
    )
    assert tuple(ingress.execution_payload) == VISIBLE_FIELDS
    assert set(ingress.execution_payload) == {
        "benchmark_id", "split", "structure_hash", "benchmark_protocol_hash"
    }
    assert not {
        "material_identity",
        "truth_class",
        "literature_evidence",
        "expected_stage_outcomes",
    } & set(ingress.execution_payload)


def test_ingress_schema_cannot_accept_sealed_truth_fields():
    with pytest.raises(TypeError):
        BlindBenchmarkIngress(
            ingress_version="known-material-blind-ingress-v1",
            benchmark_id="km-001",
            split="HELD_OUT",
            structure_hash=HASH,
            benchmark_protocol_hash="2" * 64,
            truth_class="POSITIVE",
        )


def test_ingress_rejects_unknown_split_and_invalid_hashes():
    with pytest.raises(ValueError):
        BlindBenchmarkIngress(
            ingress_version="known-material-blind-ingress-v1",
            benchmark_id="km-001",
            split="TRAIN",
            structure_hash=HASH,
            benchmark_protocol_hash="2" * 64,
        )
