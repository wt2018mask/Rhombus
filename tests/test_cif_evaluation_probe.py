from pathlib import Path

import pytest

from rhombus.transport.bvse_parameters import ANIONS, CATIONS, REGISTRY_ID
from rhombus.transport.cif_probe import prepare_cif_evaluation_probe

ROOT = Path(__file__).resolve().parents[1]
COD = ROOT / 'data/benchmarks/known_material/structures/cod'


def test_registry_extension_keeps_existing_parameters():
    assert ANIONS['O'] == (.985, 1.960, .390, 1.40, -2)
    assert ANIONS['H'] == (.750, 1.750, .380, 1.30, -1)
    assert CATIONS['Li'] == (1, .76)
    assert CATIONS['B'] == (3, .27)
    assert REGISTRY_ID == 'rhombus-owner-bvse-constants-v2'


def test_ordered_cif_probe_retains_composition():
    result = prepare_cif_evaluation_probe(COD / '1504402-latest-freeze-v1.cif')
    assert result['structure_status'] == 'RAW_ORDERED_CIF'
    assert result['raw_composition'] == result['ordered_probe_composition']
    assert result['qualification'] == 'ABSTAIN'


def test_composition_mismatch_is_not_silently_repaired():
    with pytest.raises(ValueError, match='composition or occupancy'):
        prepare_cif_evaluation_probe(COD / '1504403-latest-freeze-v1.cif')
