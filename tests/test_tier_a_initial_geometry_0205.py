"""Synthetic label-hostile initial geometry tests, optional TRAIN-only source audit."""
from __future__ import annotations

import json
import os
from pathlib import Path
import pytest

from rhombus.benchmark.tier_a_initial_geometry import (
    inspect_initial_xyz_geometry, audit_pinned_train_initial_geometry,
)


def _xyz(*, frames=5, atoms=2, species=("Li", "O"), pbc="T T T",
         lattice="5 0 0 0 5 0 0 0 5", bad_x=None,
         props="species:S:1:pos:R:3:energies:R:1:forces:R:3",
         change_lattice_at=None, label="NO_NUMERIC_LABEL_DECODING"):
    lines = []
    for frame in range(frames):
        lines.append(str(atoms))
        cell = "4 0 0 0 4 0 0 0 4" if frame == change_lattice_at else lattice
        lines.append(f'Lattice="{cell}" Properties={props} pbc="{pbc}" '
                     f'energy="{label}" free_energy=NOT_PARSED')
        for i in range(atoms):
            x = (0.1 * frame if i == 0 else 1.0)
            if bad_x is not None and (frame, i) == (1, 0):
                x = bad_x
            atom = species[i] if i < len(species) else "O"
            lines.append(f"{atom} {x} 0.0 0.0 NONNUMERIC_IGNORED_FORCE_ENERGY")
    return ("\n".join(lines) + "\n").encode("ascii")


def test_five_images_li_geometry_without_parsing_energy_or_forces():
    r = inspect_initial_xyz_geometry(_xyz())
    assert r["images"] == 5
    assert r["atoms_per_image"] == 2
    assert r["species_counts"] == {"Li": 1, "O": 1}
    assert r["cell_volume_A3"] == 125
    assert r["max_direct_consecutive_Li_A"] == pytest.approx(0.1)
    assert r["max_direct_first_to_last_Li_A"] == pytest.approx(0.4)
    assert r["decoded_fields"] == "ONLY_SPECIES_POSITION_LATTICE_PBC_NO_ENERGY_FORCE_STRESS"
    assert "NONNUMERIC_IGNORED" not in str(r)


def test_label_poison_does_not_affect_output_and_seven_images_are_supported():
    r1 = inspect_initial_xyz_geometry(_xyz(label="malformed!"))
    r2 = inspect_initial_xyz_geometry(_xyz(label="123456789.0123"))
    assert r1 == r2
    assert inspect_initial_xyz_geometry(_xyz(frames=7))["images"] == 7


@pytest.mark.parametrize("changes,expected", [
    ({"frames": 4}, "IMAGE_COUNT"),
    ({"frames": 8}, "TOO_MANY_IMAGES"),
    ({"atoms": 0}, "ATOM_COUNT"),
    ({"bad_x": "nan"}, "NONFINITE_POSITION"),
    ({"bad_x": "inf"}, "NONFINITE_POSITION"),
    ({"pbc": "T F T"}, "NONPERIODIC"),
    ({"lattice": "0 0 0 0 0 0 0 0 0"}, "SINGULAR"),
    ({"change_lattice_at": 2}, "LATTICE_CHANGED"),
    ({"props": "species:S:1:forces:R:3:pos:R:3"}, "COLUMN_POSITION"),
    ({"species": ("Na", "O")}, "NO_LITHIUM"),
])
def test_invalid_geometry_fails_closed(changes, expected):
    with pytest.raises(ValueError, match=expected):
        inspect_initial_xyz_geometry(_xyz(**changes))


def test_truncation_and_species_swapping_fail_closed():
    data = _xyz()
    with pytest.raises(ValueError, match="TRUNCATED_IMAGE"):
        inspect_initial_xyz_geometry(b"\n".join(data.splitlines()[:-2]) + b"\n")
    with pytest.raises(ValueError, match="SPECIES_OR_ATOM_ORDER_CHANGED"):
        inspect_initial_xyz_geometry(
            data.replace(b"Li 0.1 0.0 0.0", b"O 0.1 0.0 0.0", 1))


def test_ambiguous_header_and_opaque_atom_columns():
    data = _xyz().replace(b'pbc="T T T"', b'pbc="T T T" pbc="T T T"')
    with pytest.raises(ValueError, match="PBC_MISSING_OR_AMBIGUOUS"):
        inspect_initial_xyz_geometry(data)
    assert inspect_initial_xyz_geometry(_xyz())["periodic_all_axes"] is True


def test_actual_four_train_only_when_owner_supplies_original_zip():
    env = ("RHOMBUS_TIER_A_OWNER_ZIP", "RHOMBUS_TIER_A_PINNED_DRAFT",
           "RHOMBUS_TIER_A_PIN_RECEIPT")
    if not all(os.environ.get(x) for x in env):
        pytest.skip("Exact owner ZIP and pinned TRAIN-only identity receipts not on CI")
    a, b, c = [Path(os.environ[x]) for x in env]
    result = audit_pinned_train_initial_geometry(
        draft=json.loads(b.read_text()), receipt=json.loads(c.read_text()),
        owner_zip=a)
    assert result["execution_authorized"] is False
    assert result["validation_test_member_access"] == "NONE"
    assert result["energy_and_force_metadata_parsing"] == "NONE"
    assert len(result["pilot_rows"]) == 4
    assert all(row["images"] == 5 and row["atoms_per_image"] > 0
               for row in result["pilot_rows"])
