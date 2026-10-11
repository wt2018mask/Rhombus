"""0155 exact-original-CIF structural comparison and negative-claim tests."""
import hashlib
from pymatgen.core import Lattice, Structure
from scripts.science import obelix_original_si_cif_0155 as s


def cif(lattice=8.5, anion="O", occupancy=1.0):
    structure = Structure(Lattice.cubic(lattice), ["Li", {anion: occupancy}],
                          [[0, 0, 0], [0.5, 0.5, 0.5]])
    return structure.to(fmt="cif").encode("utf-8")


def test_same_geometry_is_heuristic_never_measured_sample():
    raw = cif()
    a, original = s.describe_cif(raw)
    b, pub = s.describe_cif(raw)
    diag = s.compare_geometry(a, b)
    assert original["cif_sha256"] == hashlib.sha256(raw).hexdigest()
    assert pub["parse_state"] == "PARSED"
    assert diag["composition_compatible_0p02_diagnostic"] is True
    assert diag["geometry_equivalent_heuristic"] is True
    assert diag["measured_sample_or_phase_match"] == "UNVERIFIED"


def test_wrong_chemistry_is_not_structural_match():
    a, _ = s.describe_cif(cif(anion="O"))
    b, _ = s.describe_cif(cif(anion="F"))
    diag = s.compare_geometry(a, b)
    assert diag["composition_compatible_0p02_diagnostic"] is False
    assert diag["geometry_equivalent_heuristic"] is None


def test_fractional_occupancy_preserved_without_ordering():
    structure, record = s.describe_cif(cif(occupancy=0.5))
    assert structure is not None
    assert record["fractional_sites"] > 0
    assert record["vacancy_sites"] > 0
    assert record["occupancies_preserved_no_ordering"] is True


def test_invalid_cif_stays_unknown_and_never_qualified():
    a, x = s.describe_cif(b"NOT A CIF")
    assert a is None
    assert x["parse_state"] == "REJECTED"
    assert s.compare_geometry(a, a)["measured_sample_or_phase_match"] == "UNVERIFIED"


def test_exact_previous_live_publisher_zip_pin():
    assert s.EXPECTED_VERIFIED_SHA256["experimental_cif_zip"] == (
        "dc88a0a83857b172ebe7a8194eb1b50148f117d6cddb39f1adbb628ac7d1c382")
    assert s.EXPECTED_SI_CIF == 8
    assert s.EXPECTED_TRAIN_ROWS == 2
