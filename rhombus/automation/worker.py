"""Kaggle script template. REQUEST and PROVIDER_RUN_ID are prefixed by controller."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request


def run_command(arguments, **options):
    subprocess.run(arguments, check=True, timeout=900, **options)


def verify_checkout_revision(repository, expected_revision):
    actual = subprocess.check_output(
        ['git', '-C', str(repository), 'rev-parse', 'HEAD'], text=True, timeout=30
    ).strip()
    if actual != expected_revision:
        raise RuntimeError('Source commit mismatch')


def main():
    if not Path('/kaggle/working').is_dir() or not Path('/kaggle/input').is_dir():
        raise RuntimeError('Kaggle only; local scientific execution disabled')
    if Path('/dev/nvidia0').exists() or os.environ.get('TPU_NAME'):
        raise RuntimeError('CPU policy forbids accelerators')
    work = Path('/tmp/rhombus-0201')
    work.mkdir(exist_ok=False)
    repository = work / 'source'
    run_command(['git', 'init', str(repository)])
    run_command(['git', '-C', str(repository), 'remote', 'add', 'origin', 'https://github.com/wt2018mask/Rhombus.git'])
    run_command(['git', '-C', str(repository), 'fetch', '--depth=1', 'origin', REQUEST['task']['code_revision']])
    run_command(['git', '-C', str(repository), 'checkout', '--detach', 'FETCH_HEAD'])
    verify_checkout_revision(repository, REQUEST['task']['code_revision'])
    for name, expected in REQUEST['source_inventory'].items():
        path = repository / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Source digest mismatch')
    environment = work / 'venv'
    run_command([sys.executable, '-m', 'venv', str(environment)])
    python = str(environment / 'bin/python')
    run_command([python, '-m', 'pip', '--isolated', 'install', '--index-url',
                 'https://download.pytorch.org/whl/cpu', 'torch==2.14.1+cpu'])
    run_command([python, '-m', 'pip', '--isolated', 'install', '--index-url', 'https://pypi.org/simple',
                 '-c', str(repository / 'scripts/ci/constraints.txt'), 'mace-torch==0.3.16',
                 'pymatgen==2026.9.24', 'ase==3.29.0', 'smact==4.0.2', 'pyyaml==6.0.3'])
    model = work / 'mace.model'
    with urllib.request.urlopen('https://github.com/ACEsuit/mace-mp/releases/download/mace_mpa_0/mace-mpa-0-medium.model', timeout=180) as source, model.open('xb') as output:
        count = 0
        while chunk := source.read(1048576):
            count += len(chunk)
            if count > 80000000:
                raise RuntimeError('Model size budget')
            output.write(chunk)
    if hashlib.sha256(model.read_bytes()).hexdigest() != REQUEST['protocol']['model_sha256']:
        raise RuntimeError('Model digest mismatch before deserialization')
    request_path = work / 'request.json'
    request_path.write_text(json.dumps(REQUEST), encoding='utf-8')
    driver = (
        'import json,sys; from scripts.science.thermal_study_0201 import execute_thermal_workload; '
        'execute_thermal_workload(json.load(open(sys.argv[1])),sys.argv[2],sys.argv[3],'
        'execution_origin={"mode":"POLICY_AUTOMATION","provider_job_id":sys.argv[4],'
        '"provider_attestation":"NOT_RUNTIME_ATTESTED"})'
    )
    os.environ.update(OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2')
    with Path('/kaggle/working/execution.log').open('xb') as log:
        subprocess.run([python, '-c', driver, str(request_path), str(model), '/kaggle/working/result', PROVIDER_RUN_ID],
                       cwd=repository, stdout=log, stderr=subprocess.STDOUT,
                       timeout=REQUEST['protocol']['resource_budget']['wall_seconds'], check=True)


if __name__ == '__main__':
    main()
