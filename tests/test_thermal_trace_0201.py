"""Synthetic controls only; no MLIP weights or scientific result fabrication."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from rhombus.atomistics.thermal_trace import (
    VERSION, build_thermal_trace, canonical_bytes, sha256, verify_thermal_trace, write_thermal_trace,
)
from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS, evaluate_p2, run_nvt, DiagnosticStall

ROOT = Path(__file__).resolve().parents[1]


def protocol(**changes):
    return dict(P2_PROTOCOL_DEFAULTS, **dict(base_seed=7, equil_steps=4, production_steps=12,
                sample_interval_steps=2, **changes))


def binding():
    return {"task_id": "a"*64, "candidate_id": "synthetic-control", "source_sha256": "b"*64,
            "relaxed_structure_sha256": "c"*64, "model_sha256": "d"*64,
            "protocol_sha256": "e"*64, "source_commit": "f"*40,
            "runtime": {"kind": "SYNTHETIC_NOT_MLIP"}}


def record(p=None):
    p = p or protocol()
    frames = []
    for step in range(0, p['equil_steps'] + p['production_steps'] + 1, p['sample_interval_steps']):
        potential = 1 + step * .002
        kinetic = .3 + step * .001
        frames.append(dict(md_step=step, phase='equil' if step <= p['equil_steps'] else 'production',
            positions=np.array([[0., 0, 0], [2., 2, 2]]), temperature_K=500 + step,
            energy_ev=potential, kinetic_energy_eV=kinetic, mechanical_energy_eV=potential+kinetic,
            volume_A3=1000., max_force_ev_A=.01, pressure_GPa=None, finite=True, step_jump_A=0.))
    return dict(frames=frames, species=['Li', 'O'], cell=np.eye(3)*10,
        timestep_fs=p['timestep_fs'], sample_interval_steps=p['sample_interval_steps'],
        equil_steps=p['equil_steps'], production_steps=p['production_steps'], seed=p['base_seed'],
        actual_completed_steps=p['equil_steps'] + p['production_steps'], completed=True,
        termination_note=None, thermal_trace_version=VERSION, numerical_abort=None)


def verify(tmp_path, trace, expected=None):
    artifact = write_thermal_trace(tmp_path, trace)
    return verify_thermal_trace(tmp_path / artifact['path'], expected_sha256=artifact['sha256'],
        expected_binding=expected or binding(), expected_protocol=protocol())


def test_independent_recomputation_matches_unchanged_legacy_p2(tmp_path):
    r = record()
    d = verify(tmp_path, build_thermal_trace(r, binding(), protocol()))
    _, metrics, _ = evaluate_p2(r, protocol())
    for key in ('temp_mean_K', 'temp_std_K', 'energy_mean_ev_per_atom', 'energy_drift_ev_per_ps_per_atom'):
        assert d[key] == pytest.approx(metrics[key], abs=1e-10)
    assert d['energy_drift_ev_per_ps_per_atom'] == pytest.approx(1.)
    assert d['mechanical_energy_trend_eV_per_ps_per_atom'] == pytest.approx(1.5)
    assert d['production_time_ps'] == [.006, .008, .010, .012, .014, .016]
    assert d['stationarity'] == 'NOT_ESTABLISHED'
    assert d['scientific_verdict'] == 'INDETERMINATE'
    assert 'not conserved' in d['interpretation']


@pytest.mark.parametrize('corruption', ['digest', 'model', 'protocol', 'duplicate', 'order', 'units',
    'nan', 'truncated', 'time', 'sum', 'phase', 'seed', 'false_complete'])
def test_adversarial_trace_rejected(tmp_path, corruption):
    t = build_thermal_trace(record(), binding(), protocol())
    if corruption == 'model': t['binding']['model_sha256'] = '0'*64
    if corruption == 'protocol': t['protocol']['timestep_fs'] = .5
    if corruption == 'duplicate': t['samples'][4] = t['samples'][3]
    if corruption == 'order': t['samples'][3:5] = t['samples'][3:5][::-1]
    if corruption == 'units': t['units'] = dict(t['units'], time='ps')
    if corruption == 'nan': t['samples'][4]['temperature_K'] = float('nan')
    if corruption == 'truncated': t['samples'].pop()
    if corruption == 'time': t['samples'][4]['time_fs'] += 1
    if corruption == 'sum': t['samples'][4]['mechanical_energy_eV'] += 1
    if corruption == 'phase': t['samples'][4]['phase'] = 'equil'
    if corruption == 'seed': t['seed'] += 1
    if corruption == 'false_complete': t['termination']['actual_completed_steps'] -= 2
    if corruption == 'digest':
        a = write_thermal_trace(tmp_path, t)
        path = tmp_path / a['path']; path.write_bytes(path.read_bytes() + b' ')
        with pytest.raises(ValueError, match='digest'):
            verify_thermal_trace(path, expected_sha256=a['sha256'], expected_binding=binding(), expected_protocol=protocol())
    else:
        with pytest.raises(ValueError): verify(tmp_path, t)


def test_partial_hook_abort_records_actual_end_not_configured_length(tmp_path):
    r = record(); r['completed'] = False; r['termination_note'] = 'diagnostic-stall'
    r['actual_completed_steps'] = 9; r['frames'] = r['frames'][:5]
    d = verify(tmp_path, build_thermal_trace(r, binding(), protocol()))
    assert d['operational_status'] == 'PARTIAL'
    assert d['production_time_ps'] == [.006, .008]


def test_old_data_cannot_invent_measured_kinetic_energy():
    r = record(); del r['thermal_trace_version']
    with pytest.raises(ValueError, match='original measured'):
        build_thermal_trace(r, binding(), protocol())


def test_nonfinite_abort_evidence_is_preserved_without_invented_values(tmp_path):
    r = record(); r['completed'] = False; r['termination_note'] = 'non-finite-data'
    r['frames'][-1]['energy_ev'] = float('nan')
    r['frames'][-1]['mechanical_energy_eV'] = float('nan')
    t = build_thermal_trace(r, binding(), protocol())
    a = write_thermal_trace(tmp_path, t)
    raw = json.loads((tmp_path/a['path']).read_bytes())
    assert raw['samples'][-1]['potential_energy_eV'] is None
    assert raw['samples'][-1]['invalid_measurements'] == ['potential_energy_eV', 'mechanical_energy_eV']
    with pytest.raises(ValueError, match='non-finite'):
        verify_thermal_trace(tmp_path/a['path'], expected_sha256=a['sha256'], expected_binding=binding(), expected_protocol=protocol())


def test_content_addressing_refuses_overwrite(tmp_path):
    t = build_thermal_trace(record(), binding(), protocol())
    a = write_thermal_trace(tmp_path, t)
    assert a['path'].startswith(a['sha256'])
    with pytest.raises(FileExistsError): write_thermal_trace(tmp_path, t)


def test_instrumentation_preserves_rng_positions_and_calculator_calls(tmp_path):
    from ase.calculators.calculator import Calculator, all_changes
    from pymatgen.core import Lattice, Structure
    class Harmonic(Calculator):
        implemented_properties = ['energy', 'forces']
        def __init__(self):
            super().__init__(); self.calls = 0
        def calculate(self, atoms=None, properties=('energy',), system_changes=all_changes):
            super().calculate(atoms, properties, system_changes); self.calls += 1
            x = atoms.get_positions()
            self.results = {'energy': float(.005*(x*x).sum()), 'forces': -.01*x}
    s = Structure(Lattice.cubic(10), ['Li', 'Li', 'O', 'O'], [[0,0,0],[.2,.2,.2],[.4,.4,.4],[.6,.6,.6]]).as_dict()
    a, b = Harmonic(), Harmonic(); p = protocol()
    original = run_nvt(s, a, p, 7)
    instrumented = run_nvt(s, b, p, 7, retain_thermal_trace=True)
    assert a.calls == b.calls
    assert [f['md_step'] for f in instrumented['frames']] == list(range(0,17,2))
    for x, y in zip(original['frames'], instrumented['frames']):
        np.testing.assert_array_equal(x['positions'], y['positions'])
        assert x['energy_ev'] == y['energy_ev'] and x['temperature_K'] == y['temperature_K']
        assert 'kinetic_energy_eV' not in x and y['kinetic_energy_eV'] >= 0
    t = build_thermal_trace(instrumented, binding(), p)
    assert verify(tmp_path, t)['operational_status'] == 'COMPLETE'
    def hook(step, phase):
        if step == 10: raise DiagnosticStall('synthetic hook abort')
    partial = run_nvt(s, Harmonic(), p, 7, step_hook=hook, retain_thermal_trace=True)
    assert partial['actual_completed_steps'] == 9
    assert partial['production_steps'] == 12  # historical field is configured, not actual
    assert partial['completed'] is False
    trace = build_thermal_trace(partial, binding(), p)
    other = tmp_path / 'partial'; other.mkdir()
    assert verify(other, trace)['operational_status'] == 'PARTIAL'
