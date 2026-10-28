"""One-shot owner-operated campaign journal. No provider submission operations.

The cooperative checkpoint must be called between stages and at MD steps. It
cannot interrupt a stuck native force call; an external runtime wall limit is
still required. Partial results are durable before the next expensive unit.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import time


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


class CampaignBudgetStop(RuntimeError):
    pass


class CampaignWorker:
    """Trusted callable execution plus immutable per-unit receipts, no retries."""
    def __init__(self, output_dir, *, wall_seconds=10800, clock=time.monotonic,
                 output_bytes=128*1024*1024, execution_origin='LOCAL_DIAGNOSTIC_OR_TEST'):
        if not math.isfinite(wall_seconds) or not 1 <= wall_seconds <= 10800 or not 1024 <= output_bytes <= 128*1024*1024:
            raise ValueError('bounded free CPU runtime/output budget required')
        self.root = Path(output_dir)
        if execution_origin not in ('LOCAL_DIAGNOSTIC_OR_TEST', 'OWNER_MANUAL_LAUNCH'):
            raise ValueError('explicit supported execution origin required')
        self.execution_origin = execution_origin
        self.root.mkdir(parents=True, exist_ok=False)
        self.clock, self.started = clock, clock()
        self.wall_seconds, self.output_bytes = wall_seconds, output_bytes
        self.receipts = []
        self._index = 0
        self._used = False
        self._write_manifest('PARTIAL', None)

    def _write_manifest(self, status, error_type):
        files = {}
        for path in self.root.rglob('*'):
            if path.is_symlink():
                raise ValueError('symlink in campaign output')
            if path.is_file() and path.name not in ('manifest.json', '.manifest.pending'):
                files[path.relative_to(self.root).as_posix()] = {
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size_bytes': path.stat().st_size}
        manifest = {'schema_version': 'rhombus-campaign-v3', 'status': status,
                    'receipts': self.receipts, 'files': files, 'error_type': error_type,
                    'elapsed_seconds': self.clock()-self.started,
                    'wall_budget_seconds': self.wall_seconds, 'sealing_fraction': .8,
                    'runtime': {'python': platform.python_version(), 'machine': platform.machine(),
                                'cpu_count': os.cpu_count(), 'requested_cpu_threads': 2},
                    'launch_mode': self.execution_origin,
                    'provider_attestation': 'PROVIDER_ATTESTATION_UNAVAILABLE',
                    'qualification': 'ABSTAIN', 'scientific_GO': False, 'automatic_retries': 0}
        temporary = self.root / '.manifest.pending'
        if temporary.is_symlink() or (self.root/'manifest.json').is_symlink():
            raise ValueError('unsafe journal path')
        with temporary.open('wb') as stream:
            stream.write(canonical(manifest)); stream.flush(); os.fsync(stream.fileno())
        temporary.replace(self.root/'manifest.json')
        return manifest

    def checkpoint(self, unit=None):
        """Seal a completed/partial unit BEFORE checking remaining time."""
        if unit is not None:
            raw = canonical(unit)
            used = sum(f.stat().st_size for f in self.root.rglob('*') if f.is_file())
            if used+len(raw) > self.output_bytes:
                raise CampaignBudgetStop('output limit')
            digest = hashlib.sha256(raw).hexdigest()
            name = f'{self._index:05d}-{digest}.json'
            self._index += 1
            with (self.root/name).open('xb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            self.receipts.append({'path': name, 'sha256': digest, 'size_bytes': len(raw)})
            self._write_manifest('PARTIAL', None)
        if self.clock()-self.started >= .8*self.wall_seconds:
            raise CampaignBudgetStop('80 percent sealing deadline')

    def run(self, candidates, evaluate):
        if self._used:
            raise FileExistsError('one campaign attempt only')
        self._used = True
        if len(candidates) > 32:
            raise ValueError('campaign candidate budget exceeded')
        status, error = 'COMPLETE', None
        try:
            for candidate in candidates:
                self.checkpoint()
                result = evaluate(candidate, self.checkpoint)
                self.checkpoint({'kind': 'candidate_dossier', 'candidate_id': candidate['candidate_id'], 'result': result})
        except CampaignBudgetStop:
            status, error = 'PARTIAL', 'CampaignBudgetStop'
        except Exception as exc:
            # Do not persist exception text: provider/library messages can
            # contain secrets or private paths. Retain already sealed units.
            status, error = 'FAILED', type(exc).__name__
        return self._write_manifest(status, error)


def verify_campaign(directory, *, expected_manifest_sha256):
    root = Path(directory).resolve(strict=True)
    path = root/'manifest.json'
    if path.is_symlink() or path.stat().st_size > 1024*1024:
        raise ValueError('unsafe manifest')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_manifest_sha256:
        raise ValueError('manifest identity mismatch')
    manifest = json.loads(raw)
    names = {'manifest.json'}
    for row in manifest['receipts']:
        name = row['path']; target = root/name
        if Path(name).name != name or target.is_symlink() or name in names:
            raise ValueError('unsafe or duplicate receipt')
        names.add(name)
        if target.stat().st_size != row['size_bytes'] or row['size_bytes'] > 128*1024*1024:
            raise ValueError('receipt size mismatch')
        if hashlib.sha256(target.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('receipt digest mismatch')
    for name, row in manifest['files'].items():
        target = root/name
        if Path(name).is_absolute() or '..' in Path(name).parts or any(p.is_symlink() for p in (target, *target.parents)):
            raise ValueError('unsafe artifact path')
        if target.stat().st_size != row['size_bytes'] or hashlib.sha256(target.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('artifact integrity mismatch')
        names.add(name)
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() or p.is_symlink()}
    if actual != names:
        raise ValueError('unexpected campaign output inventory')
    if manifest['status'] not in ('COMPLETE', 'PARTIAL', 'FAILED') or manifest['scientific_GO'] is not False:
        raise ValueError('invalid campaign completion semantics')
    return {'artifact_integrity': 'VERIFIED', 'status': manifest['status'],
            'provider_identity': 'PROVIDER_ATTESTATION_UNAVAILABLE',
            'qualification': 'ABSTAIN', 'receipt_count': len(manifest['receipts'])}


def validate_source_request(request, repository):
    root = Path(repository).resolve(strict=True)
    revision = request['source_commit']
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('exact source revision required')
    git = lambda *a: subprocess.check_output(['git', '--no-replace-objects', '-C', str(root), *a], text=True).strip()
    if git('rev-parse', 'HEAD') != revision:
        raise ValueError('source checkout mismatch')
    paths = git('ls-tree', '-r', '--name-only', revision).splitlines()
    required = {p for p in paths if p.endswith('.py') and p.startswith(('rhombus/', 'rudeus/'))}
    inventory = request['source_inventory']
    if not required <= set(inventory):
        raise ValueError('incomplete executable source inventory')
    for package in ('rhombus', 'rudeus'):
        if {p.relative_to(root).as_posix() for p in (root/package).rglob('*.py')} != {p for p in required if p.startswith(package+'/')}:
            raise ValueError('untracked or missing executable source')
    for name, digest in inventory.items():
        path = root/name
        if path.is_symlink() or Path(name).is_absolute() or '..' in Path(name).parts or name not in paths:
            raise ValueError('unsafe source inventory')
        raw = subprocess.check_output(['git', '--no-replace-objects', '-C', str(root), 'show', revision+':'+name])
        if hashlib.sha256(raw).hexdigest() != digest or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('source file digest mismatch')


def prepare_campaign_request(repository, revision, candidates, protocol):
    """Pin a new unsubmitted V3 request; never reuse frozen 0201 identities."""
    root = Path(repository)
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('exact committed source required')
    paths = subprocess.check_output(['git', '-C', str(root), 'ls-tree', '-r', '--name-only', revision], text=True).splitlines()
    chosen = [p for p in paths if p.startswith(('rhombus/', 'rudeus/', 'data/benchmarks/known_material/structures/'))
              or p in ('pyproject.toml', 'scripts/ci/constraints.txt')]
    inventory = {p: hashlib.sha256(subprocess.check_output(['git', '--no-replace-objects', '-C', str(root), 'show', revision+':'+p])).hexdigest()
                 for p in chosen}
    request = {'schema_version': 'rhombus-owner-campaign-request-v3', 'source_commit': revision,
               'source_inventory': inventory, 'protocol': protocol,
               'protocol_sha256': hashlib.sha256(canonical(protocol)).hexdigest(), 'candidates': candidates,
               'submission_status': 'NOT_SUBMITTED', 'automatic_retries': 0}
    request['task_id'] = hashlib.sha256(canonical(request)).hexdigest()
    return request


def consume_local_launch(runtime_directory, task_id):
    """Exclusive marker for this runtime only, never global provider authority."""
    if not re.fullmatch('[0-9a-f]{64}', task_id):
        raise ValueError('content-bound task identity required')
    marker = Path(runtime_directory)/('.rhombus-v3-'+task_id+'.consumed')
    with marker.open('x') as stream:
        stream.write(task_id+'\n'); stream.flush(); os.fsync(stream.fileno())


def run_on_kaggle(request, output_dir, *, repository, owner_launch=False):
    """Manual CPU entry point. No self-issued trusted-host or provider receipt."""
    if owner_launch is not True or not Path('/kaggle/working').is_dir() or not Path('/kaggle/input').is_dir():
        raise PermissionError('explicit owner launch inside Kaggle required; no local fallback')
    if Path('/dev/nvidia0').exists() or os.environ.get('TPU_NAME'):
        raise PermissionError('free CPU configuration required')
    if not Path(__file__).resolve().is_relative_to(Path(repository).resolve()):
        raise ValueError('executing worker is outside the pinned repository')
    validate_source_request(request, repository)
    if (request.get('automatic_retries') != 0 or request.get('submission_status') != 'NOT_SUBMITTED'
        or hashlib.sha256(canonical({k:v for k,v in request.items() if k!='task_id'})).hexdigest() != request['task_id']):
        raise ValueError('one-run request identity mismatch')
    protocol = request['protocol']
    if hashlib.sha256(canonical(protocol)).hexdigest() != request['protocol_sha256']:
        raise ValueError('campaign protocol mismatch')
    consume_local_launch('/kaggle/working', request['task_id'])
    os.environ.update(OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2')
    worker = CampaignWorker(output_dir, wall_seconds=protocol['wall_seconds'], execution_origin='OWNER_MANUAL_LAUNCH')
    from rhombus.pipeline import RhombusDiscoveryFunnel
    if protocol['mode'] not in ('STATIC_DIAGNOSTIC_CPU', 'MULTI_TEMPERATURE_MACE_CPU'):
        raise ValueError('explicit campaign mode required')
    stages = None
    if protocol['mode'] == 'MULTI_TEMPERATURE_MACE_CPU':
        from rhombus.atomistics.campaign_dynamics import KaggleMACEStages
        stages = KaggleMACEStages(protocol, checkpoint=worker.checkpoint,
                                  output_dir=worker.root/'artifacts', binding=request)
    def evaluate(candidate, checkpoint):
        checkpoint()
        funnel = RhombusDiscoveryFunnel()
        if stages is not None:
            funnel.adapters.update(stages.adapters())
        return funnel.run(candidate)
    worker.checkpoint({'kind': 'request_identity', 'request': request})
    return worker.run(request['candidates'], evaluate)


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--owner-launch', action='store_true')
    parser.add_argument('--verify-manifest-sha256')
    args = parser.parse_args()
    if args.verify_manifest_sha256:
        result = verify_campaign(args.output, expected_manifest_sha256=args.verify_manifest_sha256)
    else:
        if args.request.stat().st_size > 4*1024*1024:
            parser.error('bounded request required')
        result = run_on_kaggle(json.loads(args.request.read_bytes()), args.output,
                               repository=Path(__file__).resolve().parents[2], owner_launch=args.owner_launch)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
