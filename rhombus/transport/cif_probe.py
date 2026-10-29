"""Explicit, provenance-bearing CIF probes; no inferred experimental correction."""
import hashlib
import warnings
from pathlib import Path

from pymatgen.core import Structure


def prepare_cif_evaluation_probe(cif_path):
    """Load an ordered CIF or construct the existing bounded disorder probe.

    Parser warnings about composition or occupancy are treated as failures: a
    correction needs an independently justified structural interpretation.
    """
    path = Path(cif_path)
    raw = path.read_bytes()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        structure = Structure.from_str(raw.decode('utf-8'), 'cif')
    messages = [str(w.message) for w in caught]
    if any('Incorrect stoichiometry' in message or 'occupanc' in message.lower()
           and ('exceeded' in message.lower() or 'sum to >' in message.lower())
           for message in messages):
        raise ValueError('CIF composition or occupancy requires explicit source review')
    composition = structure.composition.element_composition.as_dict()
    defect = {}
    if structure.is_ordered:
        status = 'RAW_ORDERED_CIF'
    else:
        from rhombus.domain.archetypes import _ordered_probe
        structure, defect = _ordered_probe(structure)
        status = 'DETERMINISTIC_ORDERED_PROBE'
    return {'source_sha256': hashlib.sha256(raw).hexdigest(),
            'raw_composition': composition,
            'ordered_probe_composition': structure.composition.element_composition.as_dict(),
            'structure_status': status, 'warnings': messages,
            'structure': structure, 'defect': defect,
            'qualification': 'ABSTAIN'}
