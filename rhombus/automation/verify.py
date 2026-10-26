"""Unprivileged artifact verification; reuses the frozen thermal verifier."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

from rhombus.automation.ledger import ControlError, canonical, digest


def verify_results(directory, request, state, retrieval):
    from rhombus.atomistics.thermal_study import verify_thermal_result_artifacts
    import rhombus.atomistics.thermal_study as thermal_study
    from rhombus.evidence import Applicability, DomainStatus, EvidenceRecord, OperationalStatus, ScientificVerdict, Uncertainty
    from rhombus.evidence.identity import ArtifactBinding, ModelIdentity, ProtocolIdentity, SourceBinding
    directory = Path(directory)
    limit = request['protocol']['resource_budget']['output_bytes']
    paths = list(directory.iterdir())
    if (len(paths) > 100 or any(path.is_symlink() or not path.is_file() for path in paths)
            or sum(path.stat().st_size for path in paths) > limit):
        raise ControlError('ARTIFACT_BUDGET_OR_TYPE')
    actual = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    if actual != retrieval['files'] or retrieval['provider_run_id'] != state['provider_run_id']:
        raise ControlError('RETRIEVAL_INTEGRITY_FAILURE')
    for path in paths:
        if path.suffix == '.npz':
            with zipfile.ZipFile(path) as archive:
                if sum(item.file_size for item in archive.infolist()) > limit:
                    raise ControlError('TRAJECTORY_DECOMPRESSION_BUDGET')
    manifest = json.loads((directory / 'manifest.json').read_bytes())
    if (manifest.get('execution_origin', {}).get('mode') != 'POLICY_AUTOMATION'
            or manifest.get('qualification') != 'ABSTAIN' or manifest.get('conductivity_S_cm') is not None
            or state['request_sha256'] != digest(request)):
        raise ControlError('RESULT_IDENTITY_OR_CLAIM_MISMATCH')
    checked = verify_thermal_result_artifacts(directory, request,
        expected_manifest_sha256=actual['manifest.json'], expected_job_id=state['provider_run_id'])
    bindings = tuple(ArtifactBinding('artifact:sha256:' + value, value) for value in actual.values())
    records = []
    parent = json.loads((Path(thermal_study.__file__).resolve().parents[2] / request['protocol']['parent_report']).read_bytes())
    sources = {item['candidate_id']: item['source'] for item in parent['candidates']}
    for candidate in sorted({run['binding']['candidate_id'] for run in manifest['runs']}):
        indexed = [(index, run) for index, run in enumerate(manifest['runs']) if run['binding']['candidate_id'] == candidate]
        source = sources[candidate]
        record = EvidenceRecord.create(candidate_id=candidate, evidence_kind='AUTOMATED_THERMAL_DIAGNOSTICS',
            capability='assess_finite_temperature_stability', operational_status=OperationalStatus.SUCCEEDED,
            scientific_verdict=ScientificVerdict.INDETERMINATE,
            applicability=Applicability('digital_ionic_transport', DomainStatus.UNQUALIFIED),
            uncertainty=Uncertainty(status='UNKNOWN', reason='Model applicability, sampling, finite size and transport convergence unqualified'),
            limitations=('Provider version API observation is not runtime attestation',
                        'NVT mechanical energy is not conserved', 'P3 BLOCKED; no conductivity qualification'),
            artifact_ids=tuple(binding.artifact_id for binding in bindings), artifact_bindings=bindings,
            source_bindings=(SourceBinding('RETAINED_COD_REFERENCE_CIF', source['source_id'],
                source['pinned_locator'], indexed[0][1]['binding']['source_sha256']),),
            model_identity=ModelIdentity('medium-mpa-0', 'MACE-MPA-0', checkpoint_sha256=request['protocol']['model_sha256'],
                dtype='float64', framework='torch-2.14.1+cpu'),
            protocol_id='thermal-study-0201-v1', protocol_identity=ProtocolIdentity('thermal-study-0201-v1',
                'assess_finite_temperature_stability', 'v1', request['task']['protocol_hash']),
            provenance={'task_id': request['task_id'], 'provider_run_id': state['provider_run_id'],
                'source_commit': request['task']['code_revision'], 'policy_sha256': state['policy_sha256'],
                'provider_origin_binding': state['provider_origin_binding'], 'runtime_attestation': False},
            payload={'qualification': 'ABSTAIN', 'conductivity_S_cm': None, 'remote_workload_status': manifest['status'],
                'runs': [{'label': run['label'], 'P2_verdict': run['P2']['p2_verdict'],
                          'offline_diagnostics': checked['runs'][index]} for index, run in indexed]}).to_dict()
        records.append(record)
    return {'state': 'SCIENTIFICALLY_INDETERMINATE', 'artifact_integrity': 'VERIFIED',
            'numerical_verification': checked, 'evidence_records': records,
            'qualification': 'ABSTAIN', 'conductivity_S_cm': None}
