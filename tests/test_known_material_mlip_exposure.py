"""MLIP pretraining-exposure accounting tests."""
import json
from pathlib import Path

import pytest

from rudeus.science.known_material_mlip_exposure import (
    ExposureDisposition,
    MLIP_EXPOSURE_LEDGER_VERSION,
    load_mlip_exposure_ledger,
    validate_exposure_coverage,
)
from rudeus.science.known_material_universe import MaterialUniverseIntake

ROOT = Path("data/benchmarks/known_material")


def universe():
    return MaterialUniverseIntake.from_dict(
        json.loads((ROOT / "b2_universe_intake_v1.json").read_text(encoding="utf-8"))
    )


def test_canonical_exposure_ledger_binds_medium_mpa_0_and_full_universe():
    ledger = load_mlip_exposure_ledger(ROOT / "mlip_exposure_ledger_v1.json")
    assert ledger.ledger_version == MLIP_EXPOSURE_LEDGER_VERSION
    assert ledger.model_id == "medium-mpa-0"
    assert ledger.checkpoint_sha256 == (
        "75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638"
    )
    assert ledger.training_datasets == ("MPTrj", "sAlex")
    dispositions = validate_exposure_coverage(ledger, universe())
    assert len(dispositions) == 8
    assert set(dispositions.values()) == {
        ExposureDisposition.UNRESOLVED_EXACT_MEMBERSHIP.value
    }


def test_exposure_accounting_never_converts_unknown_membership_to_unseen_claim():
    ledger = load_mlip_exposure_ledger(ROOT / "mlip_exposure_ledger_v1.json")
    assert all(
        item.disposition != ExposureDisposition.NO_PUBLIC_MATCH.value
        for item in ledger.material_records
    )
    joined = " ".join(ledger.interpretation_constraints).lower()
    assert "must not be described as foundation-model-unseen" in joined


def test_exposure_coverage_fails_closed_if_universe_entry_is_missing():
    ledger = load_mlip_exposure_ledger(ROOT / "mlip_exposure_ledger_v1.json")
    reduced = type(ledger)(
        ledger_version=ledger.ledger_version,
        model_id=ledger.model_id,
        checkpoint_sha256=ledger.checkpoint_sha256,
        training_datasets=ledger.training_datasets,
        provenance_refs=ledger.provenance_refs,
        material_records=ledger.material_records[:-1],
        interpretation_constraints=ledger.interpretation_constraints,
    )
    with pytest.raises(ValueError, match="does not match B2 universe"):
        validate_exposure_coverage(reduced, universe())
