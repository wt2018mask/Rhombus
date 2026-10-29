"""Version 2 manual importer; execution source and verifier remain separate."""
from __future__ import annotations
import json
from pathlib import Path
import stat
import zipfile
import rhombus.atomistics.manual_thermal as manual_thermal_module
import rhombus.atomistics.thermal_study as thermal_study_module
import rhombus.atomistics.thermal_trace as thermal_trace_module

IMPORT_VERSION = 'rhombus-owner-manual-import-v2'

from rhombus.atomistics.manual_thermal import validate_manual_request
from rhombus.atomistics.thermal_study import verify_thermal_result_artifacts
from rhombus.atomistics.thermal_trace import canonical_bytes, sha256


def import_manual_result(archive_path, request, destination, *, root, expected_archive_sha256=None):
    validate_manual_request(request,root)
    archive_path=Path(archive_path);destination=Path(destination)
    limit=request['protocol']['resource_budget']['output_bytes']+1048576
    if archive_path.stat().st_size>limit:raise ValueError('archive size budget')
    archive_sha=sha256(archive_path.read_bytes())
    if expected_archive_sha256 is not None and archive_sha!=expected_archive_sha256:
        raise ValueError('download archive digest mismatch')
    if destination.exists():raise FileExistsError('preserve prior import')
    with zipfile.ZipFile(archive_path) as z:
        members=z.infolist();names=[i.filename for i in members]
        if (len(members)>100 or len(names)!=len(set(names)) or sum(i.file_size for i in members)>limit
                or any(Path(i.filename).name!=i.filename or '\\' in i.filename or i.filename in ('.','..')
                    or i.is_dir() or stat.S_ISLNK(i.external_attr>>16) or i.flag_bits&1 for i in members)):
            raise ValueError('unsafe/duplicate/traversal/archive budget')
        if 'download-manifest.json' not in names:raise ValueError('missing download manifest')
        d=json.loads(z.read('download-manifest.json'))
        if (d.get('schema_version')!='rhombus-owner-download-v1' or d['request_sha256']!=sha256(canonical_bytes(request))
                or d['task_id']!=request['task_id'] or d['launch_id']!=request['launch_id']
                or d.get('provider_attestation')!='UNAVAILABLE'
                or set(names)!=set(d['files'])|{'download-manifest.json'}):
            raise ValueError('download/request inventory mismatch')
        for name,row in d['files'].items():
            raw=z.read(name)
            if len(raw)!=row['size_bytes'] or sha256(raw)!=row['sha256']:
                raise ValueError('download artifact digest mismatch')
            # Bound the inner NPZ too before numpy decompresses it.
            if name.endswith('.npz'):
                import io
                with zipfile.ZipFile(io.BytesIO(raw)) as npz:
                    if sum(i.file_size for i in npz.infolist())>limit:
                        raise ValueError('nested trajectory decompression budget')
        if z.read('request.json')!=canonical_bytes(request):raise ValueError('returned request changed')
        destination.mkdir(parents=True)
        for member in members:
            with (destination/member.filename).open('xb') as out:out.write(z.read(member))
    verifier_sha256 = sha256(Path(__file__).read_bytes())
    dependencies = {module.__name__: sha256(Path(module.__file__).read_bytes())
                    for module in (manual_thermal_module, thermal_study_module, thermal_trace_module)}
    state={'schema_version': IMPORT_VERSION, 'importer_sha256': verifier_sha256,
           'verifier_dependency_sha256': dependencies,
           'execution_source_commit': request['task']['code_revision'],
           'launch_mode':'OWNER_MANUAL_LAUNCH','artifact_integrity':'VERIFIED',
           'provider_identity_independently_verified':False,'provider_attestation':'UNAVAILABLE',
           'remote_execution':'OWNER_REPORTED_NOT_INDEPENDENTLY_OBSERVED',
           'archive_sha256':archive_sha,'qualification':'ABSTAIN','conductivity_S_cm':None}
    manifest_path=destination/'manifest.json'
    if not d['scientific_manifest_present']:
        if manifest_path.exists() or 'failure.json' not in d['files']:
            raise ValueError('false no-science receipt')
        state.update(scientific_result='NO_SCIENTIFIC_OUTPUT',evidence_records=[])
    else:
        m=json.loads(manifest_path.read_bytes())
        origin=m.get('execution_origin',{})
        if (origin.get('mode')!='OWNER_MANUAL_LAUNCH' or origin.get('provider_attestation')!='UNAVAILABLE'
                or origin.get('launch_id')!=request['launch_id'] or m.get('job_id') is not None
                or m.get('qualification')!='ABSTAIN' or m.get('conductivity_S_cm') is not None):
            raise ValueError('manual origin cannot masquerade as authenticated dispatch or qualification')
        receipt=json.loads((destination/'owner-launch.json').read_bytes())
        if (receipt['request_sha256']!=sha256(canonical_bytes(request)) or receipt['launch_id']!=request['launch_id']
                or receipt.get('task_id')!=request['task_id']
                or receipt.get('execution_mode')!='OWNER_MANUAL_LAUNCH'
                or receipt.get('free_cpu_owner_declared') is not True
                or receipt.get('provider_attestation')!='UNAVAILABLE'
                or receipt.get('global_atomic_consumption')!='NOT_ESTABLISHED'
                or receipt.get('provider_identity_independently_verified') is not False
                or receipt.get('provider_job_id') is not None):
            raise ValueError('invalid manual launch receipt')
        if not m['runs']:
            if m['status']!='PARTIAL' or not m.get('error_type'):
                raise ValueError('empty successful scientific manifest')
            state.update(scientific_result='NO_COMPLETE_THERMAL_RUNS',evidence_records=[])
        else:
            checked=verify_thermal_result_artifacts(destination,request,
                expected_manifest_sha256=d['files']['manifest.json']['sha256'],expected_job_id=None,
                transport_metadata=('download-manifest.json',))
            if (checked['operational_status'] != m['status'] or
                (m['status'] == 'COMPLETE' and any(run.get('operational_status') != 'COMPLETE'
                                                     for run in checked['runs']))):
                raise ValueError('complete workload contains incomplete run')
            state.update(scientific_result='ARTIFACT_MATHEMATICS_VERIFIED_ORIGIN_UNATTESTED',
                         numerical_verification=checked,evidence_records=_evidence_records(m,checked,request))
    with (destination/'import-report-v2.json').open('xb') as out:out.write(canonical_bytes(state))
    with (destination/'evidence-v2.jsonl').open('xb') as out:
        for row in state['evidence_records']:out.write(canonical_bytes(row))
    return state


def _evidence_records(manifest,checked,request):
    from rhombus.evidence import (Applicability,DomainStatus,EvidenceRecord,OperationalStatus,
        ScientificVerdict,Uncertainty)
    from rhombus.evidence.identity import ArtifactBinding,ModelIdentity,ProtocolIdentity,SourceBinding
    rows=[]
    root=Path(__file__).resolve().parents[2]
    parent=json.loads((root/request['protocol']['parent_report']).read_bytes())
    sources={c['candidate_id']:c['source'] for c in parent['candidates']}
    for candidate in sorted({r['binding']['candidate_id'] for r in manifest['runs']}):
        indexed=[(i,r) for i,r in enumerate(manifest['runs']) if r['binding']['candidate_id']==candidate]
        bindings=tuple(ArtifactBinding('artifact:sha256:'+v['sha256'],v['sha256']) for v in manifest['files'].values())
        model=request['protocol']['model_sha256'];protocol=request['task']['protocol_hash']
        operation = OperationalStatus.SUCCEEDED if checked['operational_status'] == 'COMPLETE' else OperationalStatus.ERROR
        rows.append(EvidenceRecord.create(candidate_id=candidate,evidence_kind='OWNER_MANUAL_THERMAL_DIAGNOSTICS',
            capability='assess_finite_temperature_stability',operational_status=operation,
            scientific_verdict=ScientificVerdict.INDETERMINATE,
            applicability=Applicability('digital_ionic_transport',DomainStatus.UNQUALIFIED),
            uncertainty=Uncertainty(status='UNKNOWN',reason='Manual execution origin unverified; model, time and finite-size convergence unqualified'),
            limitations=('PROVIDER_ATTESTATION_UNAVAILABLE','Artifact mathematics verified, execution origin not independently attested',
                'NVT energy trend is not NVE conservation evidence','No P2.5/P3 transport qualification'),
            artifact_bindings=bindings,artifact_ids=tuple(b.artifact_id for b in bindings),
            source_bindings=(SourceBinding('RETAINED_COD_REFERENCE_CIF',sources[candidate]['source_id'],
                sources[candidate]['pinned_locator'],indexed[0][1]['binding']['source_sha256']),),
            model_identity=ModelIdentity('medium-mpa-0','MACE-MPA-0',checkpoint_sha256=model,dtype='float64',framework='torch-2.14.1+cpu'),
            protocol_id='thermal-study-0201-v1',protocol_identity=ProtocolIdentity('thermal-study-0201-v1','assess_finite_temperature_stability','v1',protocol),
            provenance={'task_id':request['task_id'],'launch_id':request['launch_id'],'source_commit':request['task']['code_revision'],
                'execution_mode':'OWNER_MANUAL_LAUNCH','provider_identity_independently_verified':False,
                'importer_version': IMPORT_VERSION, 'importer_sha256': sha256(Path(__file__).read_bytes())},
            payload={'provider_attestation':'UNAVAILABLE','operational_scope':'OFFLINE_IMPORT_DIAGNOSTICS',
                'remote_workload_status':manifest['status'],'scientific_GO':False,'qualification':'ABSTAIN',
                'conductivity_S_cm':None,'runs':[{'label':r['label'],'P2_verdict':r['P2']['p2_verdict'],
                    'offline_diagnostics':checked['runs'][i]} for i,r in indexed]}).to_dict())
    return rows
