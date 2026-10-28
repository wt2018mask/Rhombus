"""Actual CIF arithmetic and synthetic thermodynamics are explicitly distinct."""
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pytest
from pymatgen.core import Lattice, Species, Structure

from rhombus.transport.bvse_parameters import ANIONS, parameter_identity, build_site_evaluator
from rhombus.transport.static_assessment import assess_static_transport
from rhombus.generation.defect_engine import expand_supercell, seed_vacancies, substitute_aliovalent, order_fractional
from rhombus.generation.autonomous_generator import AutonomousCandidateGenerator, selection_utility
from rhombus.qualification.electronic_insulation import assess_electronic_insulation
from rhombus.atomistics.phase_stability_p1 import assess_phase_stability
from rhombus.qualification.electrochemical_window import assess_electrochemical_window
from rhombus.atomistics.campaign_dynamics import block_diffusivity, KaggleMACEStages
from rhombus.automation.campaign_worker_v3 import CampaignWorker, canonical, verify_campaign, run_on_kaggle, prepare_campaign_request, validate_source_request
from rhombus.pipeline import RhombusDiscoveryFunnel

ROOT = Path(__file__).resolve().parents[1]
STRUCTURES = ROOT/'data/benchmarks/known_material/structures'


def crystal(cod='9009060'):
    return Structure.from_file(STRUCTURES/'cod'/f'{cod}-latest-freeze-v1.cif')


def phase(formula, energy, name=None):
    return {'composition': formula, 'energy_eV': energy, 'energy_model_id': 'SYNTHETIC_TEST_ONLY',
            'reference_id': name or formula}


def test_owner_constants_are_exact_and_attribution_not_self_authenticated():
    assert ANIONS['O'] == (.985, 1.960, .390, 1.40, -2)
    identity = parameter_identity()
    assert not identity['literature_table_verified']
    assert len(identity['sha256']) == 64
    with pytest.raises(TypeError):
        ANIONS['O'] = (1, 2, 3, 4, 5)


@pytest.mark.parametrize('name,path,barrier,radius,mep,converged', [
    ('gamma', 'cod/1008166-latest-freeze-v1.cif', .6137690139729686, .42582278092569026, 1.114553591155424, False),
    ('sulfide', 'cod/9009060-latest-freeze-v1.cif', 1.1592977772461284, .4902812419677296, 5.584680253635243, True),
    ('tetragonal_not_cubic_garnet', 'literature/tetragonal-llzo-awaka-2009-nd-v1.cif', 2.733248181516722, .2188725413768844, 1.289645972873556, True),
])
def test_actual_cif_model_values_not_desired_material_labels(name, path, barrier, radius, mep, converged):
    result = assess_static_transport(Structure.from_file(STRUCTURES/path))
    assert result['barriers_eV']['3D'] == pytest.approx(barrier, abs=1e-8)
    assert result['bottleneck_radius_A'] == pytest.approx(radius, abs=1e-8)
    assert result['mep']['barrier_ev'] == pytest.approx(mep, abs=1e-8)
    assert result['mep']['converged'] is converged
    assert result['qualification'] == 'ABSTAIN'
    if name == 'gamma':
        # The requested high-barrier rejection is NOT supported by this model.
        assert result['gate_verdict'] == 'PASS_P0_5'
        assert result['calibration_status'] == 'UNQUALIFIED'


def test_vacancy_does_not_change_static_host_when_mobile_li_is_excluded():
    parent = expand_supercell(crystal())
    child = parent.copy(); child.remove_sites([0])
    points = np.random.default_rng(19).uniform(0, 10, (40, 3))
    assert build_site_evaluator(parent)(points)[0] == pytest.approx(build_site_evaluator(child)(points)[0])


def test_supercell_skew_images_and_intrinsic_charge_accounting():
    parent = crystal()
    expanded = expand_supercell(parent)
    assert min(expanded.lattice.abc) >= 9.5
    result = seed_vacancies(parent)[0]
    child = Structure.from_dict(result['structure'])
    assert len(child) == len(expanded)-1 and result['carrier_vacancy_fraction'] == pytest.approx(1/64)
    assert result['formal_charge_e'] == -1 and not result['charge_compensated']
    assert child.lattice.get_all_distances(result['vacant_fractional_targets'], child.frac_coords).min() > 1
    with pytest.raises(ValueError, match='budget'):
        expand_supercell(parent, minimum_length_A=100)
    skew = Structure([[10, 0, 0], [9.9, 1, 0], [0, 0, 10]], ['Li', 'F'], [[0, 0, 0], [.5, .5, .5]])
    safe = expand_supercell(skew)
    heights = 1/np.linalg.norm(safe.lattice.reciprocal_lattice_crystallographic.matrix, axis=1)
    assert min(heights) >= 9.5


def test_compensated_anion_doping_creates_real_empty_target():
    parent = crystal()
    index = next(i for i, s in enumerate(parent) if s.specie.symbol == 'S')
    results = substitute_aliovalent(parent, site_index=index, dopant='Cl', dopant_charge=-1, top_k=2)
    assert len(results) == 2
    for result in results:
        assert result['charge_compensated'] and result['formal_charge_e'] == 0
        assert result['carrier_vacancy_fraction'] == pytest.approx(1/8)
        assert len(Structure.from_dict(result['structure'])) == len(parent)-1
    with pytest.raises(ValueError, match='isovalent'):
        substitute_aliovalent(parent, site_index=index, dopant='Se', dopant_charge=-2)


def test_interstitial_compensation_requires_coordinates_and_rejects_collision():
    parent = Structure(Lattice.cubic(8), [Species('Li', 1), Species('P', 5), Species('O', -2), Species('O', -2), Species('O', -2)],
                       [[0, 0, 0], [.5, .5, .5], [.7, .5, .5], [.5, .7, .5], [.5, .5, .7]])
    with pytest.raises(ValueError, match='coordinates'):
        substitute_aliovalent(parent, site_index=1, dopant='Si', dopant_charge=4)
    with pytest.raises(ValueError, match='collision'):
        substitute_aliovalent(parent, site_index=1, dopant='Si', dopant_charge=4, interstitial_fractional=[[0, 0, 0]])
    row = substitute_aliovalent(parent, site_index=1, dopant='Si', dopant_charge=4,
                              interstitial_fractional=[[.2, .2, .2]])[0]
    assert row['charge_compensated'] and len(row['interstitial_fractional_sites']) == 1


def test_fractional_ordering_keeps_composition_and_charge():
    mixture = {Species('Li', 1): .5, Species('Na', 1): .5}
    structure = Structure(Lattice.cubic(8), [mixture, mixture, Species('O', -2)],
                          [[0, 0, 0], [.5, .5, .5], [.3, .3, .3]])
    rows = order_fractional(structure, top_k=2)
    assert len(rows) == 2
    assert all(Structure.from_dict(r['structure']).composition == structure.composition for r in rows)
    with pytest.raises(ValueError, match='budget'):
        order_fractional(structure, max_configurations=1)


@pytest.mark.parametrize('symbol,charge,verdict', [('Fe', 2, 'FALSIFIED_MIEC_ELECTRONIC_LEAKAGE'),
                                                ('Ti', 4, 'FLAGGED_ANODE_REDUCTION_RISK'),
                                                ('Al', 3, 'PASS_ELECTRONIC_INSULATOR')])
def test_formal_electronic_screen_is_not_bandgap_proof(symbol, charge, verdict):
    structure = Structure(Lattice.cubic(7), [Species(symbol, charge), Species('O', -2)], [[0, 0, 0], [.5, .5, .5]])
    result = assess_electronic_insulation(structure)
    assert result['gate_verdict'] == verdict
    assert result['estimated_bandgap_eV'] is None
    assert result['qualification'] == 'ABSTAIN'


@pytest.mark.parametrize('mev,verdict', [(0, 'PASS_THERMODYNAMICALLY_STABLE'),
                                     (40, 'PASS_METASTABLE_SYNTHESIZABLE'),
                                     (90, 'INDETERMINATE_HULL_MARGIN'),
                                     (120, 'FALSIFIED_HIGH_HULL_ENERGY')])
def test_hull_boundaries_and_missing_reference_energies(mev, verdict):
    refs = [phase('Li', 0), phase('S', 0), phase('Li2S', -6, 'lower-phase')]
    result = assess_phase_stability(phase('Li2S', -6+3*mev/1000, 'candidate'), refs)
    assert result['energy_above_hull_meV_atom'] == pytest.approx(mev)
    assert result['gate_verdict'] == verdict
    with pytest.raises(ValueError, match='endpoints'):
        assess_phase_stability(phase('Li2S', -6), [phase('Li', 0)])
    with pytest.raises(ValueError, match='model'):
        assess_phase_stability(dict(phase('Li2S', -6), energy_model_id='different'), refs)


def test_electrochemical_polytope_and_actual_decomposition_products():
    refs = [phase('Li', 0), phase('Ge', 0), phase('O', 0), phase('Li2O', -6), phase('GeO2', -6)]
    result = assess_electrochemical_window(phase('Li2GeO3', -13), refs)
    assert result['voltage_window_V'] == pytest.approx([1.25, 3.5])
    assert set(result['reduction_products']) == {'Ge', 'Li2O'}
    assert result['gate_verdict'] == 'MIEC_ALLOY_DECOMPOSITION_HAZARD' and result['decision'] == 'REJECT'
    assert assess_electrochemical_window(phase('Li2GeO3', 2), refs)['voltage_window_V'] is None


def test_generator_charge_balance_domains_and_hypothetical_labels():
    candidates = AutonomousCandidateGenerator().generate()
    assert {c['domain'] for c in candidates} == {'O_ONLY', 'S_ONLY', 'HALIDE'}
    assert all(c['defect']['charge_compensated'] and c['defect']['vacant_fractional_targets'] for c in candidates)
    assert all(c['origin'].startswith('HYPOTHETICAL') for c in candidates if c['domain'] == 'HALIDE')
    for c in candidates:
        assert c['qualification'] == 'ABSTAIN' and c['selection_utility']['missing_metrics']
    assert selection_utility(atom_count=10)['score'] > selection_utility(atom_count=100)['score']


def test_default_funnel_seeds_defects_and_stops_uncompensated_probe():
    result = RhombusDiscoveryFunnel().run({'candidate_id': 'actual-li2s-probe', 'domain': 'S_ONLY', 'structure': crystal().as_dict()})
    assert [o['stage'] for o in result['observations']] == ['G', 'P0']
    assert result['observations'][-1]['result']['gate_verdict'] == 'CHARGED_INTRINSIC_PROBE_REQUIRES_EXPLICIT_COMPENSATION'
    assert not result['scientific_GO']


def test_hull_rejection_is_wired_before_dynamics_with_real_compensated_structure():
    s = crystal(); index = next(i for i, a in enumerate(s) if a.specie.symbol == 'S')
    defect = substitute_aliovalent(s, site_index=index, dopant='Cl', dopant_charge=-1)[0]
    child = Structure.from_dict(defect['structure'])
    formula = child.composition.element_composition.as_dict()
    refs = [phase(e.symbol, 0) for e in child.composition.elements]
    candidate = {'candidate_id': 'unstable-synthetic-energy', 'domain': 'S_ONLY', 'structure': defect['structure'], 'defect': defect,
                 'phase_energy': phase(formula, child.num_sites*.2, 'candidate'), 'phase_references': refs, 'relaxation_verdict': 'PASS'}
    funnel = RhombusDiscoveryFunnel()
    # Bypass only the static model decision to isolate the reference-bound hull
    # gate. This synthetic energy test is not a crystal calibration receipt.
    funnel.adapters['P0_5'] = lambda c: {'decision': 'CONTINUE'}
    result = funnel.run(candidate)
    assert result['observations'][-1]['stage'] == 'P1'
    assert result['observations'][-1]['result']['gate_verdict'] == 'FALSIFIED_HIGH_HULL_ENERGY'
    assert result['compute_saved_stages'] == ['P2_MD', 'P3_ARRHENIUS']


def test_electronic_and_electrochemical_gates_reject_inside_default_funnel():
    s = Structure(Lattice.cubic(10), [Species('Li',1), Species('Li',1), Species('Fe',2), Species('S',-2), Species('S',-2)],
                  [[0,0,0],[.2,.2,.2],[.4,.4,.4],[.6,.6,.6],[.8,.8,.8]])
    defect = {'vacant_fractional_targets': [[.2,.8,.2]],
              'parent_mobile_fractional': [[0,0,0],[.2,.2,.2],[.2,.8,.2]]}
    result = RhombusDiscoveryFunnel().run({'candidate_id':'open-d', 'domain':'S_ONLY', 'structure':s.as_dict(), 'defect':defect})
    assert result['observations'][-1]['result']['gate_verdict'] == 'FALSIFIED_MIEC_ELECTRONIC_LEAKAGE'
    s.replace(2, Species('Ge',4)); s.replace(3, Species('O',-2)); s.replace(4, Species('O',-2))
    s.append(Species('O',-2), [.5,.8,.2])
    refs = [phase('Li',0),phase('Ge',0),phase('O',0),phase('Li2O',-6),phase('GeO2',-6)]
    candidate = {'candidate_id':'synthetic-esw', 'domain':'O_ONLY', 'structure':s.as_dict(), 'defect':defect,
                 'phase_energy':phase('Li2GeO3',-13), 'phase_references':refs}
    funnel = RhombusDiscoveryFunnel()
    # Isolate the real S adapter with synthetic earlier-stage outcomes. This
    # does not claim a completed real thermal qualification trajectory.
    for stage in ('P0_5','P1','P1_5','P2','P2_5','P3','X'):
        funnel.adapters[stage] = lambda c: {'decision':'CONTINUE'}
    result = funnel.run(candidate)
    assert result['observations'][-1]['stage'] == 'S'
    assert result['observations'][-1]['result']['gate_verdict'] == 'MIEC_ALLOY_DECOMPOSITION_HAZARD'
    assert not result['scientific_GO']


def test_block_diffusivity_recovers_random_walk_and_refuses_short_traces():
    rng = np.random.default_rng(15)
    x = np.cumsum(rng.normal(0, np.sqrt(.002), (1024, 16, 3)), axis=0)
    row = block_diffusivity(x, np.arange(1024)*.01, seed=9)
    assert row['diffusivity_m2_s'] == pytest.approx(1e-9, rel=.4)
    assert row['diffusivity_variance'] > 0
    with pytest.raises(ValueError):
        block_diffusivity(x[:12], np.arange(12), seed=9)


def test_campaign_seals_partial_units_before_80_percent_and_forbids_retry(tmp_path):
    now = [0.]
    worker = CampaignWorker(tmp_path/'campaign', wall_seconds=100, clock=lambda: now[0])
    calls = []
    def evaluate(candidate, checkpoint):
        calls.append(candidate['candidate_id'])
        now[0] = 81
        checkpoint({'kind': 'trajectory', 'completed': False, 'actual_steps': 17})
        raise AssertionError('budget failed to stop')
    manifest = worker.run([{'candidate_id': 'a'}, {'candidate_id': 'b'}], evaluate)
    assert manifest['status'] == 'PARTIAL' and calls == ['a'] and len(manifest['receipts']) == 1
    assert manifest['launch_mode'] == 'LOCAL_DIAGNOSTIC_OR_TEST'
    digest = hashlib.sha256((worker.root/'manifest.json').read_bytes()).hexdigest()
    verified = verify_campaign(worker.root, expected_manifest_sha256=digest)
    assert verified['provider_identity'] == 'PROVIDER_ATTESTATION_UNAVAILABLE'
    with pytest.raises(FileExistsError):
        worker.run([], evaluate)
    target = worker.root/manifest['receipts'][0]['path']; target.write_bytes(b'changed')
    with pytest.raises(ValueError):
        verify_campaign(worker.root, expected_manifest_sha256=digest)


def test_campaign_failure_preserves_previous_receipts_and_no_kaggle_local_fallback(tmp_path):
    worker = CampaignWorker(tmp_path/'campaign')
    def fail(candidate, checkpoint):
        checkpoint({'kind': 'completed_trajectory', 'completed': True})
        raise ValueError('sensitive exception text must not persist')
    manifest = worker.run([{'candidate_id': 'a'}], fail)
    assert manifest['status'] == 'FAILED' and manifest['error_type'] == 'ValueError'
    assert b'sensitive' not in (worker.root/'manifest.json').read_bytes()
    with pytest.raises(PermissionError):
        run_on_kaggle({}, tmp_path/'no-run', repository=ROOT)
    with pytest.raises(PermissionError):
        KaggleMACEStages({}, checkpoint=lambda: None, output_dir=tmp_path/'no-md', binding={})
    from rhombus.automation.campaign_worker_v3 import consume_local_launch
    consume_local_launch(tmp_path, 'a'*64)
    with pytest.raises(FileExistsError):
        consume_local_launch(tmp_path, 'a'*64)


def test_new_request_pins_all_committed_executable_bytes_and_rejects_changes(tmp_path):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(tmp_path), *args], text=True).strip()
    git('init', '-q')
    for name in ('rhombus', 'rudeus'):
        (tmp_path/name).mkdir(); (tmp_path/name/'__init__.py').write_text('')
    git('add', '.')
    git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'source')
    request = prepare_campaign_request(tmp_path, git('rev-parse', 'HEAD'), [], {'mode': 'STATIC_DIAGNOSTIC_CPU'})
    validate_source_request(request, tmp_path)
    assert request['submission_status'] == 'NOT_SUBMITTED' and request['automatic_retries'] == 0
    (tmp_path/'rhombus'/'injected.py').write_text('raise RuntimeError')
    with pytest.raises(ValueError, match='untracked'):
        validate_source_request(request, tmp_path)


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
async def test_v3_mcp_is_additive_readonly_and_cannot_dispatch(tmp_path):
    from mcp import Client
    from rhombus.mcp.catalog_v3 import build_portfolio_catalog, create_server
    evidence = tmp_path/'evidence.jsonl'; evidence.write_text('')
    candidate = {'candidate_id': 'c', 'domain': 'S_ONLY', 'qualification': 'ABSTAIN'}
    dossier = RhombusDiscoveryFunnel({}).run(candidate)
    catalog = build_portfolio_catalog([candidate], [dossier])
    path = tmp_path/'catalog.json'; path.write_bytes(canonical(catalog))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    server = create_server(evidence, portfolio_path=path, expected_sha256=digest)
    async with Client(server, raise_exceptions=True) as client:
        tools = (await client.list_tools()).tools
        assert len(tools) == 9 and all(t.annotations.read_only_hint for t in tools)
        result = await client.call_tool('generate_candidates_v3', {'domain': 'S_ONLY', 'limit': 1})
        assert result.structured_content['candidates'][0]['candidate_id'] == 'c'
        result = await client.call_tool('evaluate_funnel_v3', {'candidate_id': 'c'})
        assert not result.structured_content['scientific_GO']
        assert (await client.call_tool('generate_candidates_v3', {'code': 'submit()', 'limit': 1})).is_error
    with pytest.raises(ValueError, match='mismatch'):
        create_server(evidence, portfolio_path=path, expected_sha256='0'*64)
    from unittest.mock import Mock
    github = Mock()
    combined = create_server(evidence, portfolio_path=path, expected_sha256=digest, github=github)
    async with Client(combined, raise_exceptions=True) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        assert len(names) == 11
        assert {'request_approved_thermal_study', 'get_automated_thermal_evidence', 'generate_candidates_v3'} <= names
    github.call.assert_not_called()
