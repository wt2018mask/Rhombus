"""Bounded release assets with independent download-and-hash durability checks."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

from rhombus.automation.ledger import ControlError


def gh(arguments, *, allow_missing=False):
    result = subprocess.run(['gh', *arguments], capture_output=True, timeout=180, check=False)
    if result.returncode and not allow_missing:
        raise ControlError('GITHUB_ARCHIVE_OPERATION_FAILED')
    return result


def archive_results(directory, repository, source_commit, task_id):
    directory = Path(directory)
    files = sorted(path for path in directory.rglob('*') if path.is_file())
    if any(path.is_symlink() for path in directory.rglob('*')) or sum(path.stat().st_size for path in files) > 140 * 1024 * 1024:
        raise ControlError('ARCHIVE_BUDGET_OR_TYPE')
    secrets = [os.environ[name].encode() for name in ('KAGGLE_API_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN') if os.environ.get(name)]
    for path in files:
        raw = path.read_bytes()
        if any(secret in raw for secret in secrets):
            raise ControlError('SECRET_IN_ARCHIVE_DENIED')
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / 'evidence.zip'
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as output:
            for path in files:
                metadata = zipfile.ZipInfo(path.relative_to(directory).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                output.writestr(metadata, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
        checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
        tag = 'rhombus-evidence-' + task_id[:16] + '-' + checksum[:16]
        present = gh(['release', 'view', tag, '--repo', repository], allow_missing=True)
        if present.returncode:
            created = gh(['release', 'create', tag, '--repo', repository, '--target', source_commit,
                '--title', tag, '--notes', 'Automated computational evidence. Numerical verification and limitations are retained in the archive. No physical qualification.',
                '--draft'], allow_missing=True)
            if created.returncode:
                gh(['release', 'view', tag, '--repo', repository])
        uploaded = gh(['release', 'upload', tag, str(archive), '--repo', repository], allow_missing=True)
        readback = Path(temporary) / 'readback'
        readback.mkdir()
        gh(['release', 'download', tag, '--repo', repository, '--pattern', 'evidence.zip', '--dir', str(readback)])
        if hashlib.sha256((readback / 'evidence.zip').read_bytes()).hexdigest() != checksum:
            raise ControlError('DURABLE_ARCHIVE_READBACK_FAILED')
        gh(['release', 'edit', tag, '--repo', repository, '--draft=false'])
        return {'storage': 'GITHUB_RELEASE_ASSET', 'tag': tag, 'asset': 'evidence.zip',
                'sha256': checksum, 'readback_verified': True,
                'retention': 'NO_WORKFLOW_EXPIRY; owner deletion/provider retention remain possible',
                'url': 'https://github.com/' + repository + '/releases/download/' + tag + '/evidence.zip'}
