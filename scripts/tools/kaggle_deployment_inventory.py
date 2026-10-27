"""Read-only frozen deployment inventory; verifies committed bytes, never deploys."""
import hashlib
import json
import subprocess
from pathlib import Path
from rhombus.automation.controller import SOURCE, build_request

ROOT=Path(__file__).resolve().parents[2]

def git(*args,check=True):
    result=subprocess.run(['git','--no-replace-objects','-C',str(ROOT),*args],capture_output=True,check=check)
    return result.stdout


def inventory():
    request=build_request(); files=request['source_inventory']
    for path,expected in files.items():
        raw=git('show',SOURCE+':'+path)
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('frozen inventory mismatch: '+path)
    protocol=request['protocol']; parent=protocol['parent_report']
    raw=git('show',SOURCE+':'+parent)
    if hashlib.sha256(raw).hexdigest()!=protocol['parent_report_sha256']:raise ValueError('parent report mismatch')
    report=json.loads(raw);directory=str(Path(parent).parent)
    for relative,expected in report['artifact_files_sha256'].items():
        raw=git('show',SOURCE+':'+directory+'/'+relative)
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('frozen artifact mismatch: '+relative)
    main_sha=git('rev-parse','origin/main').decode().strip()
    reachable=subprocess.run(['git','-C',str(ROOT),'merge-base','--is-ancestor',SOURCE,main_sha]).returncode==0
    return {'schema_version':'rhombus-deployment-inventory-v1','source_commit':SOURCE,'main_sha':main_sha,
        'source_reachable_from_main':reachable,'source_files':files,
        'parent_report':parent,'parent_report_sha256':protocol['parent_report_sha256'],
        'parent_artifacts':report['artifact_files_sha256'],
        'controller_files':sorted(p.relative_to(ROOT).as_posix() for p in (ROOT/'rhombus/automation').glob('*.py'))+['rhombus/automation/policy.json','rhombus/automation/request.json','.github/workflows/kaggle-thermal-controller.yml','.github/workflows/kaggle-automation-tests.yml'],
        'status':'FROZEN_BYTES_VERIFIED_LOCALLY_SOURCE_REMOTE_RETENTION_UNATTESTED','production_readiness':'NO_GO'}

if __name__=='__main__': print(json.dumps(inventory(),sort_keys=True))
