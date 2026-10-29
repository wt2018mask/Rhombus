"""Synthetic artifacts only; no Kaggle or model execution."""
import json
import subprocess
import sys
import zipfile
import copy
from pathlib import Path
import pytest

from tests.test_owner_thermal_notebook import manual_package, synthetic_remote
from rhombus.atomistics.manual_import import import_manual_result as compatibility_import
from rhombus.atomistics.manual_import_v2 import import_manual_result as import_v2
from rhombus.atomistics.thermal_trace import canonical_bytes, sha256
from rhombus.atomistics.manual_thermal import package_manual_result
from rhombus.atomistics.manual_thermal import consume_owner_launch

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def manual_source():
    return ROOT, json.loads((ROOT/'data/development/manual0202/owner_request_v1.json').read_bytes())

def legacy_importer():
    source = subprocess.check_output(['git','show',
        'd1e6d933d429c078eb4f731670db0a7022354367:rhombus/atomistics/manual_import.py'], cwd=ROOT)
    namespace = {'__name__': 'historical_manual_import',
                 '__file__': str(ROOT/'rhombus/atomistics/manual_import.py')}
    exec(compile(source, '<frozen-0202-manual-import>', 'exec'), namespace)
    return namespace['import_manual_result']

def test_legacy_reproduces_partial_success_bug(manual_package):
    root, request, raw, archive, target = manual_package
    report = legacy_importer()(archive, request, target, root=root)
    assert report['numerical_verification']['operational_status'] == 'PARTIAL'
    assert len(report['evidence_records']) == 1
    assert report['evidence_records'][0]['operational_status'] == 'SUCCEEDED'
    assert report['provider_attestation'] == 'UNAVAILABLE'

def test_v2_revalidates_partial_without_overwriting_legacy(manual_package):
    root, request, raw, archive, target = manual_package
    before = archive.read_bytes()
    legacy = legacy_importer()(archive, request, target, root=root)
    corrected = import_v2(archive, request, target.parent/'corrected', root=root)
    row = corrected['evidence_records'][0]
    assert legacy['evidence_records'][0]['operational_status'] == 'SUCCEEDED'
    assert corrected['schema_version'] == 'rhombus-owner-manual-import-v2'
    assert corrected['archive_sha256'] == sha256(before)
    assert corrected['execution_source_commit'] == request['task']['code_revision']
    assert corrected['provider_attestation'] == 'UNAVAILABLE'
    assert corrected['numerical_verification']['operational_status'] == 'PARTIAL'
    assert row['operational_status'] == 'ERROR' and row['payload']['remote_workload_status'] == 'PARTIAL'
    assert row['scientific_verdict'] == 'INDETERMINATE' and row['payload']['qualification'] == 'ABSTAIN'
    assert row['payload']['conductivity_S_cm'] is None
    assert archive.read_bytes() == before
    assert (target/'import-report.json').exists() and (target.parent/'corrected'/'import-report-v2.json').exists()
    from rhombus.tools import ReadOnlyEvidenceTools
    response = ReadOnlyEvidenceTools(target.parent/'corrected'/'evidence-v2.jsonl').call_tool(
        'get_candidate_evidence', {'candidate_id': row['candidate_id']})
    assert response['claim_authorized'] is False
    with pytest.raises(FileExistsError):
        import_v2(archive, request, target.parent/'corrected', root=root)

def test_compatibility_module_uses_v2(manual_package):
    root, request, raw, archive, target = manual_package
    report = compatibility_import(archive, request, target, root=root)
    assert report['schema_version'] == 'rhombus-owner-manual-import-v2'
    assert report['evidence_records'][0]['operational_status'] == 'ERROR'

def test_v2_empty_package_is_not_success(tmp_path, manual_source):
    root, request = manual_source
    archive = tmp_path/'empty.zip'
    package_manual_result(tmp_path/'raw', request, tmp_path/'missing.log', archive)
    report = import_v2(archive, request, tmp_path/'out', root=root)
    assert report['scientific_result'] == 'NO_SCIENTIFIC_OUTPUT' and not report['evidence_records']

def test_v2_partial_manifest_with_zero_runs_has_no_records(tmp_path, manual_source):
    root, request = manual_source
    raw=tmp_path/'raw'; raw.mkdir()
    (raw/'manifest.json').write_bytes(canonical_bytes({
        'status':'PARTIAL','runs':[],'error_type':'synthetic_abort',
        'job_id':None,'qualification':'ABSTAIN','conductivity_S_cm':None,
        'execution_origin':{'mode':'OWNER_MANUAL_LAUNCH','provider_attestation':'UNAVAILABLE',
                            'launch_id':request['launch_id']}}))
    receipt=consume_owner_launch(tmp_path,request,confirmation=request['launch_id'],free_cpu_confirmed=True)
    (raw/'owner-launch.json').write_bytes(canonical_bytes(receipt))
    archive=tmp_path/'empty-manifest.zip'
    package_manual_result(raw,request,tmp_path/'none.log',archive)
    report=import_v2(archive,request,tmp_path/'imported',root=root)
    assert report['scientific_result']=='NO_COMPLETE_THERMAL_RUNS'
    assert report['evidence_records']==[]

@pytest.mark.parametrize('attack', ['false_complete', 'forged_provider', 'bad_model', 'bad_archive'])
def test_v2_rejects_forged_or_corrupt_archives(manual_package, attack):
    root, request, raw, archive, target = manual_package
    with zipfile.ZipFile(archive) as z:
        files = {name: z.read(name) for name in z.namelist()}
    if attack == 'bad_archive':
        files[next(name for name in files if name.endswith('.npz'))] += b'corrupt'
    else:
        manifest = json.loads(files['manifest.json'])
        if attack == 'false_complete': manifest['status'] = 'COMPLETE'
        if attack == 'forged_provider': manifest['job_id'] = 'forged/provider/1'
        if attack == 'bad_model': manifest['runs'][0]['binding']['model_sha256'] = '0'*64
        files['manifest.json'] = canonical_bytes(manifest)
        download = json.loads(files['download-manifest.json'])
        download['files']['manifest.json'] = {'size_bytes': len(files['manifest.json']), 'sha256': sha256(files['manifest.json'])}
        files['download-manifest.json'] = canonical_bytes(download)
    bad = target.parent/'forged.zip'
    with zipfile.ZipFile(bad, 'x') as z:
        for name, data in files.items(): z.writestr(name, data)
    with pytest.raises(ValueError): import_v2(bad, request, target, root=root)

def test_v2_cli_from_checkout(manual_package):
    root, request, raw, archive, target = manual_package
    result = subprocess.run([sys.executable, '-m', 'scripts.tools.import_manual_thermal_v2',
                             '--archive', str(archive), '--output-dir', str(target)],
                            cwd=root, text=True, capture_output=True, check=True)
    assert 'evidence-v2.jsonl' in result.stdout
    assert json.loads((target/'import-report-v2.json').read_bytes())['evidence_records'][0]['operational_status'] == 'ERROR'

@pytest.fixture
def complete_package(tmp_path, manual_source):
    from pymatgen.core import Structure
    from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS, build_p2_result, protocol_config_hash
    from rudeus.mlip.sharding import structure_dict_sha256
    from rhombus.atomistics.thermal_trace import VERSION, build_thermal_trace, write_thermal_trace
    root, request = manual_source
    p = request['protocol']
    parent = json.loads((root/p['parent_report']).read_bytes())
    candidates = {c['candidate_id']: c for c in parent['candidates']}
    plan = [(p['probe']['candidate_id'], 'cpu_probe', p['probe'])]
    for candidate in p['candidate_ids']:
        for cfg in p['study']['runs']:
            dt = cfg['timestep_fs']
            plan.append((candidate, cfg['label'], dict(cfg, equil_steps=int(p['study']['equilibration_time_fs']/dt),
                production_steps=int(p['study']['production_time_fs']/dt),
                sample_interval_steps=int(p['study']['sampling_time_fs']/dt))))
    runtime = {'packages': p['runtime_pins'], 'device':'cpu', 'dtype':'float64', 'threads':2, 'test_only':True}
    raw = tmp_path/'complete'; raw.mkdir()
    runs = []
    for index, (candidate, label, cfg) in enumerate(plan):
        c = candidates[candidate]; structure = Structure.from_dict(c['P1']['relaxed_structure_dict'])
        md = dict(P2_PROTOCOL_DEFAULTS, base_seed=cfg['seed'], timestep_fs=cfg['timestep_fs'],
                  equil_steps=cfg['equil_steps'], production_steps=cfg['production_steps'],
                  sample_interval_steps=cfg['sample_interval_steps'])
        end = md['equil_steps'] + md['production_steps']
        record = dict(species=[site.specie.symbol for site in structure], cell=structure.lattice.matrix,
            frames=[], timestep_fs=md['timestep_fs'], sample_interval_steps=md['sample_interval_steps'],
            equil_steps=md['equil_steps'], production_steps=md['production_steps'], seed=cfg['seed'],
            completed=True, termination_note=None, numerical_abort=None, wall_clock_s=0.,
            actual_completed_steps=end, thermal_trace_version=VERSION)
        for step in range(0, end+1, md['sample_interval_steps']):
            record['frames'].append(dict(phase='equil' if step<=md['equil_steps'] else 'production', md_step=step,
                positions=structure.cart_coords, temperature_K=550., energy_ev=1., kinetic_energy_eV=.5,
                mechanical_energy_eV=1.5, volume_A3=structure.volume, pressure_GPa=None,
                max_force_ev_A=.1, finite=True, step_jump_A=0.))
        b = {'task_id':request['task_id'], 'candidate_id':candidate, 'source_sha256':c['source']['artifact_sha256'],
            'relaxed_structure_sha256':structure_dict_sha256(c['P1']['relaxed_structure_dict']),
            'model_sha256':p['model_sha256'], 'protocol_sha256':request['task']['protocol_hash'],
            'source_commit':request['task']['code_revision'], 'runtime':runtime}
        trace = write_thermal_trace(raw, build_thermal_trace(record,b,md))
        batch = 'synthetic' + str(index)
        job = dict(batch_id=batch, child_material_id=candidate, parent_id='synthetic-control',
            relaxed_structure_sha256=b['relaxed_structure_sha256'], p2_protocol=md,
            p2_config_hash=protocol_config_hash(md), seed=cfg['seed'])
        result = build_p2_result(job, record, {'checkpoint_sha256':p['model_sha256']}, traj_artifact_dir=raw)
        runs.append({'label':label,'binding':b,'md_protocol':md,'trace':trace,'P2':result,
                     'trajectory':{'path':batch+'.npz','logical_sha256':result['trajectory_artifact']['sha256']}})
    manifest = {'task_id':request['task_id'],'request_sha256':sha256(canonical_bytes(request)),
        'job_id':None,'status':'COMPLETE','runtime':runtime,'runs':runs,'qualification':'ABSTAIN',
        'conductivity_S_cm':None,'execution_origin':{'mode':'OWNER_MANUAL_LAUNCH',
            'provider_attestation':'UNAVAILABLE','launch_id':request['launch_id']}}
    (raw/'manifest.json').write_bytes(canonical_bytes(manifest))
    receipt = consume_owner_launch(tmp_path, request, confirmation=request['launch_id'], free_cpu_confirmed=True)
    (raw/'owner-launch.json').write_bytes(canonical_bytes(receipt))
    archive=tmp_path/'complete.zip'
    package_manual_result(raw, request, tmp_path/'none.log', archive)
    return root, request, archive, tmp_path/'imported'

def test_v2_complete_full_synthetic_plan(complete_package):
    root, request, archive, target = complete_package
    result=import_v2(archive,request,target,root=root)
    assert result['numerical_verification']['operational_status']=='COMPLETE'
    assert len(result['numerical_verification']['runs']) == 7
    assert all(row['operational_status']=='SUCCEEDED' for row in result['evidence_records'])
    assert all(row['scientific_verdict']=='INDETERMINATE' for row in result['evidence_records'])
    assert result['provider_attestation']=='UNAVAILABLE' and result['qualification']=='ABSTAIN'

def test_complete_cannot_hide_independently_detected_partial_run(complete_package, monkeypatch):
    import rhombus.atomistics.manual_import_v2 as importer
    root, request, archive, target = complete_package
    real_verifier = importer.verify_thermal_result_artifacts
    def partial_run(*args, **kwargs):
        checked = real_verifier(*args, **kwargs)
        checked['runs'][-1]['operational_status'] = 'PARTIAL'
        return checked
    monkeypatch.setattr(importer, 'verify_thermal_result_artifacts', partial_run)
    with pytest.raises(ValueError, match='complete workload contains incomplete run'):
        importer.import_manual_result(archive, request, target, root=root)

def test_complete_synthetic_plan_also_passes_automated_verifier(complete_package, tmp_path):
    from rhombus.automation.controller import build_request
    from rhombus.automation.ledger import digest
    from rhombus.automation.verify import verify_results
    root, manual, archive, _ = complete_package
    request = build_request()
    output = tmp_path/'automatic'; output.mkdir()
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            if info.filename != 'download-manifest.json':
                (output/info.filename).write_bytes(z.read(info))
    manifest=json.loads((output/'manifest.json').read_bytes())
    job='synthetic/NOT-A-KAGGLE-RUN/1'
    manifest.update(task_id=request['task_id'], request_sha256=digest(request), job_id=job,
                    execution_origin={'mode':'POLICY_AUTOMATION','provider_attestation':'SYNTHETIC_NOT_KAGGLE'})
    for run in manifest['runs']:
        b=run['binding']; b['task_id']=request['task_id']; b['source_commit']=request['task']['code_revision']
        old=output/run['trace']['path']; trace=json.loads(old.read_bytes()); old.unlink(); trace['binding']=b
        data=canonical_bytes(trace); name=sha256(data)+'.thermal.json'; (output/name).write_bytes(data)
        run['trace']={'path':name,'sha256':sha256(data),'size_bytes':len(data)}
    manifest['files']={p.name:{'sha256':sha256(p.read_bytes()),'size_bytes':p.stat().st_size}
                       for p in output.iterdir() if p.name!='manifest.json'}
    (output/'manifest.json').write_bytes(canonical_bytes(manifest))
    state={'provider_run_id':job,'request_sha256':digest(request),'policy_sha256':'a'*64,
           'provider_origin_binding':'SYNTHETIC_NOT_KAGGLE'}
    retrieval={'provider_run_id':job,'files':{p.name:sha256(p.read_bytes()) for p in output.iterdir()}}
    result=verify_results(output, request, state, retrieval)
    assert result['numerical_verification']['operational_status']=='COMPLETE'
    assert all(row['operational_status']=='SUCCEEDED' for row in result['evidence_records'])
    assert result['qualification']=='ABSTAIN' and result['conductivity_S_cm'] is None
