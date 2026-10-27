"""Build a disposable main-based candidate from committed Git blobs only.

This copies no credentials and changes no refs. It does not make a deployment
PR or authorize execution. The frozen science checkout remains separate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
MAIN='1aaaa555a9a1ce2c9123845402fec4e664626708'
EXTRA=('rhombus/tools/mcp_server.py','scripts/tools/kaggle_0203_readiness.py',
       'scripts/tools/validate_kaggle_bootstrap.py','.github/workflows/kaggle-thermal-controller.yml',
       '.github/workflows/kaggle-automation-tests.yml')


def build(destination, revision):
    destination=Path(destination)
    if destination.exists():raise FileExistsError('preserve existing rehearsal')
    def git(*args):return subprocess.check_output(['git','--no-replace-objects','-C',str(ROOT),*args])
    if git('cat-file','-t',revision).strip()!=b'commit':raise ValueError('source must be a commit')
    subprocess.run(['git','clone','--quiet','--no-hardlinks','--no-checkout',str(ROOT),str(destination)],check=True)
    subprocess.run(['git','-C',str(destination),'checkout','--quiet','--detach',MAIN],check=True)
    files=git('ls-tree','-r','--name-only',revision,'rhombus/automation').decode().splitlines()+list(EXTRA)
    hashes={}
    for name in files:
        raw=git('show',revision+':'+name)
        p=destination/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        hashes[name]=hashlib.sha256(raw).hexdigest()
    return {'schema_version':'rhombus-release-rehearsal-v1','main_sha':MAIN,'source_commit':revision,
            'candidate_files_sha256':hashes,'production_readiness':'NO_GO','production_mutations':0}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--destination',type=Path,required=True)
    p.add_argument('--source-commit',required=True);a=p.parse_args()
    print(json.dumps(build(a.destination,a.source_commit),sort_keys=True))

if __name__=='__main__':main()
