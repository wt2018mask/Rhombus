"""COD source-adapter verification tests."""
import pytest

from rudeus.science.known_material_structure_import import (
    COD_LICENSE,
    CodArtifactSpec,
    sha256_bytes,
    verify_cod_cif_payload,
)


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
