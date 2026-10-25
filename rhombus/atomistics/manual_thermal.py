"""One owner-operated notebook launch, separate from trusted-host dispatch."""
from __future__ import annotations

import json
import os
from pathlib import Path

from rudeus.execution.contracts import TaskSpec
from rudeus.science.contracts import digest
from rhombus.atomistics.thermal_study import (PROTOCOL_PATH, build_study_task, load_protocol,
    prepare_thermal_study, source_inventory)
from rhombus.atomistics.thermal_trace import canonical_bytes, sha256

PRIOR_REQUEST = 'data/development/digital0201/prepared_request_v1.json'
MANUAL_VERSION = 'rhombus-owner-manual-thermal-v1'


def build_manual_request(root, revision):
    request = prepare_thermal_study(root, revision)
    request.update(manual_version=MANUAL_VERSION, execution_mode='OWNER_MANUAL_LAUNCH',
        prior_request_sha256=sha256((Path(root)/PRIOR_REQUEST).read_bytes()),
        launch_id=digest({'task_id':request['task_id'], 'path':MANUAL_VERSION}),
        owner_launch_required=True, provider_attestation='UNAVAILABLE',
        duplicate_scope='Exclusive persistent working-directory marker only; no cross-session provider ledger')
    return request


def validate_manual_request(request, root):
    task = TaskSpec.from_dict(request['task']); task.validate()
    inventory = source_inventory(root, task.code_revision)
    protocol = load_protocol(root)
    if (request.get('manual_version') != MANUAL_VERSION or request.get('execution_mode') != 'OWNER_MANUAL_LAUNCH'
            or request.get('owner_launch_required') is not True
            or request.get('provider_attestation') != 'UNAVAILABLE'
            or request.get('provider_job_id') is not None or request.get('submission_gate') != 'CLOSED'
            or request.get('state') != 'PREPARED_NOT_SUBMITTED'
            or request['task_id'] != task.task_id or request['protocol'] != protocol
            or request['source_inventory'] != inventory
            or task.to_dict() != build_study_task(protocol, task.code_revision, inventory).to_dict()
            or request['prior_request_sha256'] != sha256((Path(root)/PRIOR_REQUEST).read_bytes())
            or request['launch_id'] != digest({'task_id':task.task_id, 'path':MANUAL_VERSION})
            or inventory[PROTOCOL_PATH] != sha256((Path(root)/PROTOCOL_PATH).read_bytes())):
        raise ValueError('manual request/source/prior/protocol identity mismatch')
    required = {'scripts/kaggle/owner_thermal_run.py', 'scripts/kaggle/build_owner_thermal_notebook.py'}
    if not required <= inventory.keys():
        raise ValueError('manual entry points must be committed')
    return task


def consume_owner_launch(marker_dir, request, *, confirmation, free_cpu_confirmed):
    """A local one-shot marker, NOT authenticated global atomic consumption.

    The owner must not launch the same request in a fresh session/notebook.
    Reissuing a consumed/failed request requires a separately reviewed request.
    """
    if confirmation != request['launch_id'] or free_cpu_confirmed is not True:
        raise PermissionError('explicit owner launch and free CPU confirmation required')
    target = Path(marker_dir) / ('rhombus-once-' + request['launch_id'] + '.json')
    receipt = {'schema_version':MANUAL_VERSION, 'execution_mode':'OWNER_MANUAL_LAUNCH',
        'task_id':request['task_id'], 'launch_id':request['launch_id'],
        'request_sha256':sha256(canonical_bytes(request)), 'free_cpu_owner_declared':True,
        'provider_job_id':None, 'provider_identity_independently_verified':False,
        'provider_attestation':'UNAVAILABLE', 'global_atomic_consumption':'NOT_ESTABLISHED'}
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(canonical_bytes(receipt)); out.flush(); os.fsync(out.fileno())
    return receipt


def package_manual_result(output, request, log_path, archive_path):
    """Finalize a downloadable bounded package after the child has stopped."""
    import zipfile
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    archive_path=Path(archive_path)
    if archive_path.exists():raise FileExistsError('preserve earlier download package')
    marker=output.parent/('rhombus-once-'+request['launch_id']+'.json')
    if marker.exists() and not (output/'owner-launch.json').exists():
        with (output/'owner-launch.json').open('xb') as out:out.write(marker.read_bytes())
    for name,raw in [('request.json',canonical_bytes(request))]:
        with (output/name).open('xb') as out:out.write(raw)
    log_path=Path(log_path)
    if log_path.exists():
        with log_path.open('rb') as source:
            source.seek(max(0,log_path.stat().st_size-1048576))
            with (output/'execution.log').open('xb') as out:out.write(source.read(1048576))
    manifest_path=output/'manifest.json'
    if manifest_path.exists():
        m=json.loads(manifest_path.read_bytes())
        if m.get('execution_origin',{}).get('mode')!='OWNER_MANUAL_LAUNCH' or m.get('job_id') is not None:
            raise ValueError('manual package cannot carry controlled-host receipt')
        m['files']={p.name:{'sha256':sha256(p.read_bytes()),'size_bytes':p.stat().st_size}
                    for p in output.iterdir() if p.is_file() and p.name!='manifest.json'}
        manifest_path.write_bytes(canonical_bytes(m))
    else:
        with (output/'failure.json').open('xb') as out:
            out.write(canonical_bytes({'status':'NO_SCIENTIFIC_OUTPUT', 'task_id':request['task_id'],
                'execution_mode':'OWNER_MANUAL_LAUNCH','provider_attestation':'UNAVAILABLE'}))
    files={p.name:{'sha256':sha256(p.read_bytes()),'size_bytes':p.stat().st_size}
           for p in output.iterdir() if p.is_file()}
    if sum(r['size_bytes'] for r in files.values())>request['protocol']['resource_budget']['output_bytes']:
        raise ValueError('download package exceeds frozen output budget; retain raw files')
    download={'schema_version':'rhombus-owner-download-v1','request_sha256':sha256(canonical_bytes(request)),
        'task_id':request['task_id'],'launch_id':request['launch_id'], 'files':files,
        'scientific_manifest_present':manifest_path.exists(),'provider_attestation':'UNAVAILABLE',
        'execution_log_tail_limit_bytes':1048576}
    with (output/'download-manifest.json').open('xb') as out:out.write(canonical_bytes(download))
    with zipfile.ZipFile(archive_path,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path.is_file():archive.write(path,path.name)
    return {'archive':str(archive_path),'archive_sha256':sha256(archive_path.read_bytes()),
            'manifest_sha256':sha256(manifest_path.read_bytes()) if manifest_path.exists() else None,
            'provider_attestation':'UNAVAILABLE'}
