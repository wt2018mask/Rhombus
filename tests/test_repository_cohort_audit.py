from pathlib import Path

from rhombus.transport.cohort_audit import assess, inventory


def test_inventory_and_screen_are_reproducible():
    root = Path(__file__).resolve().parents[1]
    first, failures = inventory(root, limit=1)
    second, _ = inventory(root, limit=1)
    assert first[0]['structure_sha256'] == second[0]['structure_sha256']
    assert first[0]['category'] == 'VERIFIED_BENCHMARK_CIF_OR_JSON'
    result = assess(first[0])
    assert result['qualification'] == 'ABSTAIN'
    assert result['static_verdict'] == 'STATIC_SCREENING_INCONCLUSIVE'
    assert result['x_vac'] is None
    assert not failures


def test_inventory_records_distinct_provenance_and_failures():
    root = Path(__file__).resolve().parents[1]
    rows, failures = inventory(root, limit=7)
    assert {row['category'] for row in rows} == {
        'VERIFIED_BENCHMARK_CIF_OR_JSON', 'ARCHETYPE_OR_ORDERED_PROBE',
        'ORDERED_EXPANSION_OR_BATCH_CANDIDATE'}
    assert len({row['structure_sha256'] for row in rows}) == len(rows)
    assert any('1504403' in failure['path'] for failure in failures)


def test_new_ions_keep_formal_screen_conservative():
    from pymatgen.core import Lattice, Structure
    from rhombus.qualification.electronic_insulation import assess_electronic_insulation
    from rhombus.transport.bvse_parameters import CATIONS
    assert CATIONS['Hf'] == (4, .71)
    assert CATIONS['Ba'] == (2, 1.35)
    host = Structure(Lattice.cubic(5), ['Li', 'Ba', 'O'], [[0, 0, 0], [.5, .5, .5], [.25, .25, .25]])
    assert assess_electronic_insulation(host)['gate_verdict'] == 'PASS_ELECTRONIC_INSULATOR'
    host.replace(1, 'Bi')
    assert assess_electronic_insulation(host)['gate_verdict'] == 'FLAGGED_ANODE_REDUCTION_RISK'
