"""Offline COD structure import verification tests."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from rudeus.science.known_material_structure_binding import (
    StructureArtifactState,
    StructureBindingLedger,
)
from rudeus.science.known_material_structure_import import (
    COD_LICENSE,
    CodArtifactSpec,
    apply_cod_retention_receipt,
    retain_cod_cif_payload,
    sha256_bytes,
    verify_cod_cif_payload,
)


LEDGER = Path("data/benchmarks/known_material/b2_structure_binding_v1.json")


def llzo_spec():
    return CodArtifactSpec(
        material_key="llzo-cubic-al-stabilized",
        cod_id="7215448",
        revision=176453,
        expected_formula="Al0.196 La3 Li6.06 O12 Zr2",
        expected_space_group_number=230,
    )


def payload(*, cod_id="7215448", formula="Al0.196 La3 Li6.06 O12 Zr2", sg="230"):
    return f"""data_7215448
_cod_database_code {cod_id}
_chemical_formula_sum '{formula}'
_space_group_IT_number {sg}
loop_
_atom_site_label
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Li1 0.0 0.0 0.0
""".encode("utf-8")


def ledger():
    return StructureBindingLedger.from_dict(
        json.loads(LEDGER.read_text(encoding="utf-8"))
    )


def test_cod_spec_is_revision_pinned_and_cc0():
    spec = llzo_spec()
    assert spec.source_id == "cod:7215448@176453"
    assert spec.pinned_locator.endswith("/7215448.cif@176453")
    assert COD_LICENSE == "CC0-1.0"


def test_cod_verifier_returns_sha_without_rewriting_bytes():
    raw = payload()
    assert verify_cod_cif_payload(raw, llzo_spec()) == sha256_bytes(raw)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (payload(cod_id="0000000"), "database identity mismatch"),
        (payload(formula="Li7 La3 O12 Zr2"), "formula mismatch"),
        (payload(sg="142"), "space-group mismatch"),
    ],
)
def test_cod_verifier_fails_closed_on_identity_mismatch(raw, message):
    with pytest.raises(ValueError, match=message):
        verify_cod_cif_payload(raw, llzo_spec())


def test_cod_verifier_requires_fractional_coordinates():
    raw = b"""data_7215448
_cod_database_code 7215448
_chemical_formula_sum 'Al0.196 La3 Li6.06 O12 Zr2'
_space_group_IT_number 230
"""
    with pytest.raises(ValueError, match="fractional atomic coordinates"):
        verify_cod_cif_payload(raw, llzo_spec())


def test_empty_artifact_has_no_hash_identity():
    with pytest.raises(ValueError, match="empty"):
        sha256_bytes(b"")


def test_retain_cod_cif_preserves_exact_bytes_and_emits_receipt(tmp_path):
    raw = payload()
    destination = tmp_path / "7215448-r176453.cif"
    receipt = retain_cod_cif_payload(raw, llzo_spec(), destination)
    assert destination.read_bytes() == raw
    assert receipt.artifact_sha256 == sha256_bytes(raw)
    assert receipt.byte_count == len(raw)
    assert receipt.source_id == "cod:7215448@176453"
    assert receipt.license_id == COD_LICENSE


def test_cod_receipt_promotes_only_to_retained_and_preserves_science_blockers(tmp_path):
    raw = payload()
    receipt = retain_cod_cif_payload(
        raw,
        llzo_spec(),
        tmp_path / "7215448-r176453.cif",
    )
    receipt = replace(
        receipt,
        retained_path="data/benchmarks/known_material/structures/cod/7215448-r176453.cif",
    )
    original = ledger()
    updated = apply_cod_retention_receipt(original, receipt)
    entry = next(
        item for item in updated.entries
        if item.material_key == "llzo-cubic-al-stabilized"
    )
    assert entry.artifact_state == StructureArtifactState.ARTIFACT_RETAINED.value
    assert entry.artifact_sha256 == sha256_bytes(raw)
    assert entry.retained_path == receipt.retained_path
    assert "artifact_not_yet_retained_and_hashed" not in entry.blockers
    assert "fractional_Li_Al_occupancy_execution_policy_required" in entry.blockers
    assert not updated.b2_structure_closure_authorized


def test_cod_receipt_cannot_cross_bind_to_other_source(tmp_path):
    raw = payload()
    receipt = retain_cod_cif_payload(
        raw,
        llzo_spec(),
        tmp_path / "7215448-r176453.cif",
    )
    receipt = replace(
        receipt,
        retained_path="data/benchmarks/known_material/structures/cod/7215448-r176453.cif",
    )
    forged = replace(receipt, source_id="cod:0000000@1")
    with pytest.raises(ValueError, match="source identity differs"):
        apply_cod_retention_receipt(ledger(), forged)
