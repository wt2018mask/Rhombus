"""Synthetic end-to-end notebook/download/import tests; NO Kaggle or MLIP run."""
import ast
import copy
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

import pytest

from tests.test_kaggle_thermal_0201 import synthetic_remote
from rhombus.atomistics.manual_thermal import (build_manual_request,consume_owner_launch,
    package_manual_result,validate_manual_request)
from rhombus.atomistics.manual_import import import_manual_result
from rhombus.atomistics.thermal_trace import canonical_bytes,sha256
from scripts.kaggle.build_owner_thermal_notebook import build_notebook,notebook_bytes,BOOTSTRAP
from scripts.kaggle.owner_thermal_run import launch
from rudeus.execution.contracts import ExecutionError
from rhombus.atomistics.thermal_study import submit_thermal_study,verify_remote_thermal_result

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def manual_source(tmp_path_factory):
    root=tmp_path_factory.mktemp('synthetic-committed-source')
    for name in ('rhombus','rudeus'):
        shutil.copytree(ROOT/name,root/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('scripts/science/thermal_study_0201.py','scripts/kaggle/owner_thermal_run.py',
        'scripts/kaggle/build_owner_thermal_notebook.py','scripts/ci/constraints.txt','pyproject.toml','config.yaml',
        'data/development/digital0201/protocol_v1.json','data/development/digital0201/prepared_request_v1.json'):
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    subprocess.run(['git','init','-q',str(root)],check=True)
    subprocess.run(['git','-C',str(root),'add','.'],check=True)
    subprocess.run(['git','-C',str(root),'-c','user.name=synthetic-test','-c','user.email=test@example.invalid','commit','-qm','Synthetic source inventory only'],check=True)
    revision=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD']).decode().strip()
    request=build_manual_request(root,revision)
    return root,request


def test_notebook_is_valid_deterministic_and_source_bound(manual_source):
    root,r=manual_source
    validate_manual_request(r,root)
    n=build_notebook(r)
    assert n['nbformat']==4 and n['nbformat_minor']==5
    assert n['metadata']['accelerator']=='none'
    for cell in n['cells']:
        assert cell['id'] and cell['metadata']=={}
        if cell['cell_type']=='code':
            assert cell['outputs']==[] and cell['execution_count'] is None
            ast.parse(''.join(cell['source']))
    assert notebook_bytes(r)==notebook_bytes(copy.deepcopy(r))
    assert 'host_context' not in notebook_bytes(r).decode()
    tree=ast.parse(BOOTSTRAP)
    node=next(n for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='request_bytes')
    assert eval(compile(ast.Expression(node.value),'<test>','eval'),{'json':json,'REQUEST':r})==canonical_bytes(r)
    assert r['prior_request_sha256']==sha256((ROOT/'data/development/digital0201/prepared_request_v1.json').read_bytes())
    assert r['task']['code_revision']!=json.loads((ROOT/'data/development/digital0201/prepared_request_v1.json').read_bytes())['task']['code_revision']


@pytest.mark.parametrize('field',['protocol','source','prior','mode'])
def test_changed_manual_request_rejected(manual_source,field):
    root,r=manual_source;r=copy.deepcopy(r)
    if field=='protocol':r['protocol']['probe']['production_steps']+=1
    if field=='source':r['source_inventory']['scripts/kaggle/owner_thermal_run.py']='0'*64
    if field=='prior':r['prior_request_sha256']='0'*64
    if field=='mode':r['execution_mode']='CONTROLLED_HOST'
    with pytest.raises(ValueError):validate_manual_request(r,root)


def test_owner_once_marker_requires_confirmation_and_rejects_duplicate(tmp_path,manual_source):
    _,r=manual_source
    with pytest.raises(PermissionError):consume_owner_launch(tmp_path,r,confirmation='yes',free_cpu_confirmed=True)
    receipt=consume_owner_launch(tmp_path,r,confirmation=r['launch_id'],free_cpu_confirmed=True)
    assert receipt['provider_identity_independently_verified'] is False
    assert receipt['global_atomic_consumption']=='NOT_ESTABLISHED'
    with pytest.raises(FileExistsError):consume_owner_launch(tmp_path,r,confirmation=r['launch_id'],free_cpu_confirmed=True)


def test_manual_cannot_fall_back_to_local_or_enable_submit(tmp_path,manual_source):
    _,r=manual_source
    with pytest.raises(PermissionError,match='Kaggle'):
        launch(r,tmp_path/'model',tmp_path/'output',confirmation=r['launch_id'],free_cpu_confirmed=True)
    assert not (tmp_path/'output').exists()
    with pytest.raises(ExecutionError):submit_thermal_study(r,manual=True,authorized=True)


@pytest.fixture
def manual_package(synthetic_remote,manual_source,tmp_path):
    directory,old,m,o,_=synthetic_remote
    root,r=manual_source
    raw=tmp_path/'raw';raw.mkdir()
    for p in list(directory.iterdir()):
        if p.is_file():p.rename(raw/p.name)
    m['task_id']=r['task_id'];m['request_sha256']=sha256(canonical_bytes(r));m['job_id']=None
    m['qualification']='ABSTAIN';m['conductivity_S_cm']=None
    m['execution_origin']={'mode':'OWNER_MANUAL_LAUNCH','provider_job_id':None,
        'provider_attestation':'UNAVAILABLE','launch_id':r['launch_id']}
    run=m['runs'][0];b=run['binding'];b['task_id']=r['task_id'];b['source_commit']=r['task']['code_revision']
    # Rebind explicitly synthetic measurements, never pretend they came from Kaggle.
    old_trace=raw/run['trace']['path'];trace=json.loads(old_trace.read_bytes());trace['binding']=b
    old_trace.unlink();trace_raw=canonical_bytes(trace);trace_name=sha256(trace_raw)+'.thermal.json'
    (raw/trace_name).write_bytes(trace_raw);run['trace']={'path':trace_name,'sha256':sha256(trace_raw),'size_bytes':len(trace_raw)}
    (raw/'manifest.json').write_bytes(canonical_bytes(m))
    receipt=consume_owner_launch(tmp_path,r,confirmation=r['launch_id'],free_cpu_confirmed=True)
    (raw/'owner-launch.json').write_bytes(canonical_bytes(receipt))
    log=tmp_path/'synthetic.log';log.write_text('SYNTHETIC TEST: no Kaggle or model execution\n')
    archive=tmp_path/'result.zip';package_manual_result(raw,r,log,archive)
    return root,r,raw,archive,tmp_path/'imported'


def test_download_import_to_existing_evidence_query(manual_package):
    root,r,raw,archive,target=manual_package
    result=import_manual_result(archive,r,target,root=root,expected_archive_sha256=sha256(archive.read_bytes()))
    assert result['artifact_integrity']=='VERIFIED'
    assert result['scientific_result']=='ARTIFACT_MATHEMATICS_VERIFIED_ORIGIN_UNATTESTED'
    assert result['provider_attestation']=='UNAVAILABLE'
    assert result['provider_identity_independently_verified'] is False
    assert len(result['evidence_records'])==1
    from rhombus.tools import ReadOnlyEvidenceTools
    row=result['evidence_records'][0]
    delivered=ReadOnlyEvidenceTools(target/'evidence-v2.jsonl').call_tool('get_candidate_evidence',{'candidate_id':row['candidate_id']})
    assert delivered['claim_authorized'] is False
    assert row['scientific_verdict']=='INDETERMINATE'
    assert row['payload']['conductivity_S_cm'] is None


def test_manual_outputs_cannot_become_controlled_host_receipt(manual_package):
    root,r,raw,archive,target=manual_package
    with pytest.raises(ValueError):
        verify_remote_thermal_result(raw,r,trusted_observation={'provider':'kaggle','task_id':r['task_id'],
            'status':'COMPLETE','job_id':'FABRICATED','manifest_sha256':sha256((raw/'manifest.json').read_bytes())})


@pytest.mark.parametrize('attack',['digest','traversal','duplicate','missing','altered','provider','false_complete','structure'])
def test_adversarial_download_import(manual_package,attack):
    root,r,raw,archive,target=manual_package
    if attack=='digest':
        with pytest.raises(ValueError,match='digest'):
            import_manual_result(archive,r,target,root=root,expected_archive_sha256='0'*64)
        return
    with zipfile.ZipFile(archive) as z:files={n:z.read(n) for n in z.namelist()}
    if attack=='traversal':files['../escape']=b'bad'
    if attack=='missing':del files[next(n for n in files if n.endswith('.npz'))]
    if attack=='altered':files[next(n for n in files if n.endswith('.thermal.json'))]+=b'bad'
    if attack in ('provider','false_complete','structure'):
        m=json.loads(files['manifest.json'])
        if attack=='provider':m['job_id']='FABRICATED'
        if attack=='false_complete':m['status']='COMPLETE'
        if attack=='structure':m['runs'][0]['P2']['host_framework_metrics']['host_rmsd_final_A']=42
        files['manifest.json']=canonical_bytes(m)
        d=json.loads(files['download-manifest.json'])
        d['files']['manifest.json']={'sha256':sha256(files['manifest.json']),'size_bytes':len(files['manifest.json'])}
        files['download-manifest.json']=canonical_bytes(d)
    bad=archive.parent/'bad.zip'
    with zipfile.ZipFile(bad,'x') as z:
        for name,data in files.items():z.writestr(name,data)
        if attack=='duplicate':z.writestr('request.json',files['request.json'])
    with pytest.raises(ValueError):import_manual_result(bad,r,target,root=root)


def test_pre_model_failure_package_is_importable_without_science(tmp_path,manual_source):
    root,r=manual_source
    archive=tmp_path/'failure.zip';output=tmp_path/'raw'
    package_manual_result(output,r,tmp_path/'absent.log',archive)
    result=import_manual_result(archive,r,tmp_path/'import',root=root)
    assert result['scientific_result']=='NO_SCIENTIFIC_OUTPUT' and result['evidence_records']==[]


def test_imported_synthetic_snapshot_real_mcp_subprocess(manual_package):
    import asyncio,sys
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    root,r,raw,archive,target=manual_package
    report=import_manual_result(archive,r,target,root=root)
    row=report['evidence_records'][0]
    async def retrieve():
        params=StdioServerParameters(command=sys.executable,args=['-m','rhombus.tools.mcp_server',
            '--evidence-jsonl',str(target/'evidence-v2.jsonl')],cwd=ROOT)
        with (target/'test-only-mcp-stderr.log').open('w') as error:
            async with stdio_client(params,errlog=error) as streams:
                async with ClientSession(*streams,read_timeout_seconds=20) as client:
                    await client.initialize();assert len((await client.list_tools()).tools)==6
                    for tool in ('get_candidate_evidence','build_evidence_manifest'):
                        response=await client.call_tool(tool,{'candidate_id':row['candidate_id']})
                        data=response.model_dump(mode='json',by_alias=True)
                        assert not data['isError'] and data['structuredContent']['claim_authorized'] is False
                        if tool=='get_candidate_evidence':
                            assert data['structuredContent']['evidence_records'][0]['evidence_id']==row['evidence_id']
                            assert data['structuredContent']['evidence_records'][0]['scientific_verdict']=='INDETERMINATE'
    asyncio.run(retrieve())


def test_retained_owner_release_matches_pinned_source_and_original_protocol():
    request=json.loads((ROOT/'data/development/manual0202/owner_request_v1.json').read_bytes())
    validate_manual_request(request,ROOT)
    assert (ROOT/'notebooks/Rhombus_0201_Kaggle_CPU.ipynb').read_bytes()==notebook_bytes(request)
    old=json.loads((ROOT/'data/development/digital0201/prepared_request_v1.json').read_bytes())
    assert request['protocol']==old['protocol']
    assert request['task']['protocol_hash']==old['task']['protocol_hash']
    assert request['task']['code_revision']!=old['task']['code_revision']
    assert 'scripts/tools/import_manual_thermal.py' in request['source_inventory']
