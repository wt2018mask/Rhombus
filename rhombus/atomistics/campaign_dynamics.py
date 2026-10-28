"""Kaggle-only MACE stages reusing canonical P2/P2.5, never dispatched by MCP."""
import hashlib
import importlib.metadata
import math
import os
from pathlib import Path
import numpy as np


def block_diffusivity(unwrapped_mobile, times_ps, *, seed, blocks=4, bootstrap=200):
    """Block-resample time origins of host-corrected MSD; SI D variance."""
    positions, times = np.asarray(unwrapped_mobile, float), np.asarray(times_ps, float)
    if (positions.ndim != 3 or positions.shape[2] != 3 or not positions.shape[1]
        or len(positions) != len(times) or len(times) < 64
        or not np.isfinite(positions).all() or not np.isfinite(times).all()
        or not np.allclose(np.diff(times), times[1]-times[0]) or times[1] <= times[0]
        or not 4 <= blocks <= 16 or not 50 <= bootstrap <= 1000):
        raise ValueError('bounded uniformly sampled block trajectory required')
    lags = np.arange(1, len(times)//4+1)
    origins = np.arange(len(times)-lags[-1])
    curves = []
    for chunk in np.array_split(origins, blocks):
        if len(chunk) < 8:
            raise ValueError('insufficient independent origin blocks')
        curves.append([np.mean(np.sum((positions[chunk+k]-positions[chunk])**2, axis=2)) for k in lags])
    curves = np.array(curves)
    fit = slice(len(lags)//3, None)
    lag_times = lags*(times[1]-times[0])
    estimate = lambda curve: float(np.polyfit(lag_times[fit], curve[fit], 1)[0]/6*1e-8)
    d = estimate(curves.mean(axis=0))
    rng = np.random.default_rng(seed)
    samples = [estimate(curves[rng.integers(0, blocks, blocks)].mean(axis=0)) for _ in range(bootstrap)]
    variance = float(np.var(samples, ddof=1))
    if d <= 0 or variance <= 0 or not math.isfinite(d+variance):
        raise ValueError('unresolved diffusivity or variance')
    return {'diffusivity_m2_s': d, 'diffusivity_variance': variance,
            'method': 'HOST_CORRECTED_MSD_BLOCK_ORIGIN_BOOTSTRAP',
            'block_count': blocks, 'bootstrap_count': bootstrap, 'qualification': 'ABSTAIN'}


class KaggleMACEStages:
    def __init__(self, protocol, *, checkpoint, output_dir, binding):
        if not Path('/kaggle/working').is_dir() or not Path('/kaggle/input').is_dir():
            raise PermissionError('Kaggle runtime required; no local MLIP fallback')
        self.protocol, self.checkpoint, self.binding = protocol, checkpoint, binding
        self.output = Path(output_dir)
        self.output.mkdir(exist_ok=False)
        self.calc = None
        temperatures = protocol['temperatures_K']; seeds = protocol['seeds']
        if (not 3 <= len(temperatures) <= 6 or len(set(temperatures)) != len(temperatures)
            or not all(isinstance(t, (float, int)) and 0 < t <= 1500 for t in temperatures)
            or max(temperatures)-min(temperatures) < 150
            or not 2 <= len(seeds) <= 4 or len(set(seeds)) != len(seeds)
            or any(type(s) is not int or not 0 <= s < 2**31 for s in seeds)):
            raise ValueError('explicit bounded multi-temperature/multi-seed protocol required')
        md = protocol['md']
        if (set(md) != {'equil_steps', 'production_steps', 'timestep_fs', 'sample_interval_steps'}
            or any(type(md[k]) is not int for k in ('equil_steps', 'production_steps', 'sample_interval_steps'))
            or not 1 <= md['equil_steps'] <= 2000 or not 1 <= md['production_steps'] <= 10000
            or not .1 <= md['timestep_fs'] <= 2 or not 1 <= md['sample_interval_steps'] <= 100
            or not 1 <= protocol['relaxation_max_steps'] <= 200 or not 1 <= protocol['mep_max_steps'] <= 20):
            raise ValueError('bounded new campaign scientific protocol required')
        model = Path(protocol['model_path'])
        if (model.is_symlink() or not model.resolve().is_relative_to(Path('/kaggle/input').resolve())
            or model.stat().st_size > 80000000
            or protocol['model_sha256'] != '75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638'
            or hashlib.sha256(model.read_bytes()).hexdigest() != protocol['model_sha256']):
            raise ValueError('frozen MACE model mismatch before deserialization')
        if not {'torch', 'mace-torch', 'numpy', 'ase', 'pymatgen'} <= set(protocol.get('runtime_pins', {})):
            raise ValueError('exact runtime pins required')
        for package, version in protocol['runtime_pins'].items():
            if importlib.metadata.version(package) != version:
                raise ValueError('runtime pin mismatch: '+package)

    def calculator(self):
        if self.calc is None:
            import torch
            torch.set_num_threads(2)
            from mace.calculators import MACECalculator
            self.calc = MACECalculator(model_paths=self.protocol['model_path'], device='cpu', default_dtype='float64')
        self.checkpoint()
        return self.calc

    def adapters(self):
        return {'P1': self.relax, 'P1_5': self.mep, 'P2': self.dynamics}

    def relax(self, context):
        from rhombus.pipeline.scientific_adapters import current_structure
        from rhombus.atomistics.phase_stability_p1 import assess_phase_stability
        from pymatgen.io.ase import AseAtomsAdaptor
        from ase.optimize import FIRE
        if not context.get('phase_references'):
            return {'decision': 'ABSTAIN', 'gate_verdict': 'COMPETING_PHASE_REFERENCE_ENERGIES_REQUIRED'}
        structure = current_structure(context)
        atoms = AseAtomsAdaptor.get_atoms(structure)
        atoms.calc = self.calculator()
        optimizer = FIRE(atoms, logfile=None)
        optimizer.attach(self.checkpoint, interval=1)
        converged = optimizer.run(fmax=.05, steps=self.protocol['relaxation_max_steps'])
        relaxed = AseAtomsAdaptor.get_structure(atoms)
        energy = {'composition': relaxed.composition.element_composition.as_dict(),
                  'energy_eV': float(atoms.get_potential_energy()),
                  'energy_model_id': self.protocol['model_sha256'], 'reference_id': context['candidate_id']+'-relaxed'}
        result = assess_phase_stability(energy, context['phase_references'])
        result.update(structure=relaxed.as_dict(), phase_energy=energy, relaxation_converged=bool(converged),
                      relaxation_scope='FIXED_CELL_ATOMIC_RELAXATION')
        if not converged:
            result['decision'] = 'ABSTAIN'
        self.checkpoint({'kind': 'relaxation', 'candidate_id': context['candidate_id'], 'result': result})
        return result

    def mep(self, context):
        from pymatgen.io.ase import AseAtomsAdaptor
        from rhombus.pipeline.scientific_adapters import current_structure
        from rhombus.transport.neb_pathway import ASEMobileIonEvaluator, ClimbingImageMEPSolver
        s = current_structure(context)
        targets = context['G']['defect'].get('vacant_fractional_targets', [])
        if not targets:
            return {'decision': 'ABSTAIN', 'gate_verdict': 'VACANCY_TARGET_REQUIRED'}
        index = min((i for i, a in enumerate(s) if a.specie.symbol == 'Li'),
                    key=lambda i: s.lattice.get_distance_and_image(s[i].frac_coords, targets[0])[0])
        _, image = s.lattice.get_distance_and_image(s[index].frac_coords, targets[0])
        evaluator = ASEMobileIonEvaluator(AseAtomsAdaptor.get_atoms(s), index, self.calculator(), allow_evaluation=True)
        def forces(points):
            self.checkpoint()
            return evaluator(points)
        result = ClimbingImageMEPSolver().solve(s[index].coords, s.lattice.get_cartesian_coords(np.array(targets[0])+image),
                                                forces, max_steps=self.protocol['mep_max_steps'])
        result['decision'] = 'ABSTAIN' if not result['converged'] else 'REJECT' if result['barrier_ev'] > 1 else 'CONTINUE'
        self.checkpoint({'kind': 'mep', 'candidate_id': context['candidate_id'], 'result': result})
        return result

    def dynamics(self, context):
        from rhombus.pipeline.scientific_adapters import current_structure
        from rhombus.atomistics.thermal_trace import build_thermal_trace, write_thermal_trace
        from rhombus.transport.classify import classify_transport_regime
        from rhombus.transport.window_diagnostics import multi_origin_msd
        from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS, DiagnosticStall, run_nvt, build_p2_result, protocol_config_hash, unwrap_trajectory
        from rudeus.mlip.sharding import structure_dict_sha256
        structure = current_structure(context)
        records = []
        for temperature in self.protocol['temperatures_K']:
            for seed in self.protocol['seeds']:
                self.checkpoint()
                cfg = dict(P2_PROTOCOL_DEFAULTS, **self.protocol['md'])
                cfg.update(temperature_K=temperature, base_seed=seed)
                def budget(step, phase):
                    from rhombus.automation.campaign_worker_v3 import CampaignBudgetStop
                    try:
                        self.checkpoint()
                    except CampaignBudgetStop as exc:
                        raise DiagnosticStall('campaign sealing deadline') from exc
                raw_structure = structure.as_dict()
                record = run_nvt(raw_structure, self.calculator(), cfg, seed, step_hook=budget, retain_thermal_trace=True)
                binding = {'task_id': self.binding['task_id'], 'candidate_id': context['candidate_id'],
                           'source_sha256': context.get('source_sha256') or structure_dict_sha256(raw_structure),
                           'relaxed_structure_sha256': structure_dict_sha256(raw_structure),
                           'model_sha256': self.protocol['model_sha256'], 'protocol_sha256': self.binding['protocol_sha256'],
                           'source_commit': self.binding['source_commit'], 'runtime': self.protocol['runtime_pins']}
                trace = write_thermal_trace(self.output, build_thermal_trace(record, binding, cfg))
                batch = hashlib.sha256(f'{context["candidate_id"]}-{temperature}-{seed}'.encode()).hexdigest()[:24]
                job = {'batch_id': batch, 'child_material_id': context['candidate_id'], 'parent_id': context['template_id'],
                       'relaxed_structure_sha256': binding['relaxed_structure_sha256'], 'p2_protocol': cfg,
                       'p2_config_hash': protocol_config_hash(cfg), 'seed': seed}
                result = build_p2_result(job, record, {'checkpoint_name': 'medium-mpa-0', 'checkpoint_sha256': self.protocol['model_sha256']},
                                         traj_artifact_dir=self.output)
                unit = {'kind': 'trajectory', 'candidate_id': context['candidate_id'], 'temperature_K': temperature,
                        'seed': seed, 'trace': trace, 'P2': result, 'termination_completed': record['completed']}
                # Preserve raw output before budget or scientific insufficiency stops analysis.
                self.checkpoint(unit)
                if result['p2_verdict'] != 'PASS':
                    return {'decision': 'ABSTAIN', 'gate_verdict': 'P2_NOT_PASSED', 'thermal_records': records}
                classification = classify_transport_regime(stability_payload={'batch_id': batch, 'result': result})
                frames = [f for f in record['frames'] if f['phase'] == 'production']
                x = unwrap_trajectory(np.array([f['positions'] for f in frames]), np.array(record['cell']))
                indices = np.array([s == 'Li' for s in record['species']])
                times = np.array([f['md_step'] for f in frames])*record['timestep_fs']/1000
                diagnostic = multi_origin_msd(x[:, indices], x[:, ~indices], times, host_limit_angstrom=.5)
                if classification['transport_state'] != 'DIFFUSIVE' or diagnostic['regime'] != 'DIFFUSIVE_FICKIAN':
                    self.checkpoint({'kind': 'regime', 'candidate_id': context['candidate_id'], 'legacy': classification, 'diagnostic': diagnostic})
                    return {'decision': 'ABSTAIN', 'gate_verdict': 'DIFFUSIVE_SAMPLING_NOT_ESTABLISHED', 'thermal_records': records}
                corrected = x[:, indices]-(x[:, ~indices].mean(axis=1)-x[0, ~indices].mean(axis=0))[:, None, :]
                estimate = block_diffusivity(corrected, times, seed=seed)
                row = dict(estimate, temperature_K=temperature, seed=seed, p2_verdict='PASS', regime='DIFFUSIVE_FICKIAN')
                records.append(row)
                self.checkpoint({'kind': 'diffusivity', 'candidate_id': context['candidate_id'], 'record': row})
        return {'decision': 'CONTINUE', 'gate_verdict': 'MEASURED_P2_PASSED', 'thermal_records': records}
