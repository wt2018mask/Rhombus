"""Preparation and synthetic retrieval controls, not Kaggle execution receipts."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from rudeus.execution.contracts import ExecutionError, TaskSpec
from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS, build_p2_result, protocol_config_hash
from rudeus.mlip.sharding import structure_dict_sha256
from rhombus.atomistics.thermal_study import load_protocol, prepare_thermal_study, submit_thermal_study, verify_remote_thermal_result
from rhombus.atomistics.thermal_trace import VERSION, build_thermal_trace, canonical_bytes, sha256, write_thermal_trace
from scripts.science.thermal_study_0201 import execute_on_kaggle, validate_request

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('attempt', range(3))
def test_all_dispatch_and_duplicate_retries_stay_closed(attempt):
    with pytest.raises(ExecutionError, match='submission CLOSED'):
        submit_thermal_study(authorized=True, free=True, attempt=attempt)


def test_no_local_model_execution_or_self_approved_request(tmp_path):
    with pytest.raises(PermissionError, match='trusted-host'):
        execute_on_kaggle({'authorization': True}, tmp_path/'no-model', tmp_path/'output')
    assert not (tmp_path/'output').exists()


def test_missing_committed_runner_preparation_rejected():
    with pytest.raises(ValueError, match='committed source|runner must be committed'):
        prepare_thermal_study(ROOT, '549c94aa6e9906271e08555d4e20d7449148e6da')


def test_source_revision_must_be_literal_commit():
    from rhombus.atomistics.thermal_study import source_inventory
    with pytest.raises(ValueError, match='exact source commit'):
        source_inventory(ROOT, 'main; execute')


def test_kernel_is_cpu_only_and_legacy_submission_unchanged():
    p = load_protocol(ROOT)
    assert p['device'] == 'cpu'
    assert p['resource_budget']['money_usd'] == 0
    assert p['nve'].startswith('NOT_TESTED') and p['finite_size'].startswith('NOT_TESTED')
    legacy = json.loads((ROOT/'data/development/phase3_salex_kaggle_launch_v1.json').read_bytes())
    assert legacy['armed'] is False
    assert legacy['submission_policy']['manual_submit_enabled'] is False
    assert legacy['submission_policy']['automatic_launch_enabled'] is False


@pytest.fixture
def synthetic_remote(tmp_path):
    p = load_protocol(ROOT)
    request = {'task_id': 'a'*64, 'task': {'protocol_hash': sha256((ROOT/'data/development/digital0201/protocol_v1.json').read_bytes()), 'code_revision': 'f'*40}, 'protocol': p}
    parent = json.loads((ROOT/p['parent_report']).read_bytes())
    c = parent['candidates'][0]
    cfg = p['probe']
    md = dict(P2_PROTOCOL_DEFAULTS, base_seed=cfg['seed'], timestep_fs=cfg['timestep_fs'], equil_steps=cfg['equil_steps'], production_steps=cfg['production_steps'], sample_interval_steps=cfg['sample_interval_steps'])
    from pymatgen.core import Structure
    structure = Structure.from_dict(c['P1']['relaxed_structure_dict'])
    r = dict(species=[site.specie.symbol for site in structure], cell=structure.lattice.matrix,
             frames=[], timestep_fs=md['timestep_fs'], sample_interval_steps=md['sample_interval_steps'], equil_steps=md['equil_steps'], production_steps=md['production_steps'], seed=md['base_seed'], completed=True, termination_note=None, numerical_abort=None, wall_clock_s=0., actual_completed_steps=30, thermal_trace_version=VERSION)
    for step in range(0,31,2):
        r['frames'].append(dict(phase='equil' if step<=10 else 'production', md_step=step,
            positions=structure.cart_coords, temperature_K=550.+step, energy_ev=1.+.001*step,
            kinetic_energy_eV=.5, mechanical_energy_eV=1.5+.001*step, volume_A3=structure.volume,
            pressure_GPa=None, max_force_ev_A=.1, finite=True, step_jump_A=0.))
    runtime = {'packages': p['runtime_pins'], 'device': 'cpu', 'dtype': 'float64', 'threads': 2, 'test_only': True}
    b = {'task_id': request['task_id'], 'candidate_id': c['candidate_id'], 'source_sha256': c['source']['artifact_sha256'], 'relaxed_structure_sha256': structure_dict_sha256(c['P1']['relaxed_structure_dict']), 'model_sha256': p['model_sha256'], 'protocol_sha256': request['task']['protocol_hash'], 'source_commit': request['task']['code_revision'], 'runtime': runtime}
    artifact = write_thermal_trace(tmp_path, build_thermal_trace(r,b,md))
    job = dict(batch_id='synthetic0201', child_material_id=c['candidate_id'], parent_id='synthetic-control', relaxed_structure_sha256=b['relaxed_structure_sha256'], p2_protocol=md, p2_config_hash=protocol_config_hash(md), seed=cfg['seed'])
    result = build_p2_result(job, r, {'checkpoint_sha256':p['model_sha256']}, traj_artifact_dir=tmp_path)
    manifest = {'task_id':request['task_id'], 'request_sha256':sha256(canonical_bytes(request)), 'job_id':'SYNTHETIC_NOT_KAGGLE', 'status':'PARTIAL', 'runtime':runtime,
        'runs':[{'label':'cpu_probe','binding':b,'md_protocol':md,'trace':artifact,'P2':result,'trajectory':{'path':'synthetic0201.npz','logical_sha256':result['trajectory_artifact']['sha256']}}]}
    observation = {'provider':'kaggle','task_id':request['task_id'],'status':'COMPLETE','job_id':manifest['job_id']}
    def reseal():
        manifest['files']={f.name:{'sha256':sha256(f.read_bytes()),'size_bytes':f.stat().st_size} for f in tmp_path.iterdir() if f.name!='manifest.json'}
        (tmp_path/'manifest.json').write_bytes(canonical_bytes(manifest))
        observation['manifest_sha256']=sha256((tmp_path/'manifest.json').read_bytes())
    reseal()
    return tmp_path,request,manifest,observation,reseal


def test_synthetic_retrieval_recomputes_metrics_without_model(synthetic_remote):
    directory,request,manifest,observation,_ = synthetic_remote
    report = verify_remote_thermal_result(directory,request,trusted_observation=observation)
    assert report['operational_status']=='PARTIAL'
    assert report['qualification']=='ABSTAIN' and report['conductivity_S_cm'] is None
    assert report['runs'][0]['temp_mean_K']==pytest.approx(571.)


@pytest.mark.parametrize('attack',['producer_receipt','digest','wrong_job','orphan','model','protocol','summary','false_complete','runtime','trajectory_steps'])
def test_adversarial_remote_retrieval(synthetic_remote,attack):
    directory,request,m,o,reseal=synthetic_remote
    if attack=='producer_receipt': o=None
    if attack=='digest': o['manifest_sha256']='0'*64
    if attack=='wrong_job': o['job_id']='false-run'
    if attack=='orphan': m['runs'][0]['trace']['path']='absent.thermal.json'; reseal()
    if attack=='model': m['runs'][0]['binding']['model_sha256']='0'*64; reseal()
    if attack=='protocol': m['runs'][0]['md_protocol']['temperature_K']=900; reseal()
    if attack=='summary': m['runs'][0]['P2']['thermal_metrics']['temp_mean_K']=999; reseal()
    if attack=='false_complete': m['status']='COMPLETE'; reseal()
    if attack=='runtime': m['runtime']['device']='cuda'; reseal()
    if attack=='trajectory_steps': m['runs'][0]['P2']['p2_config_hash']='bad'; reseal()
    with pytest.raises(ValueError): verify_remote_thermal_result(directory,request,trusted_observation=o)
