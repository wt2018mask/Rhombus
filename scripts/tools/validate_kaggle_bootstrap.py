"""Offline Git root inspection; never provisions a branch or confers authority."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from rhombus.automation.ledger import INITIAL_LEDGER, canonical


def inspect_root(repo, commit):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('full lowercase SHA-1 commit required')
    def git(*args):
        return subprocess.check_output(['git','--no-replace-objects','-C',str(repo),*args],stderr=subprocess.DEVNULL)
    if git('cat-file','-t',commit).strip()!=b'commit':
        raise ValueError('not a commit')
    parents=git('rev-list','--parents','-n','1',commit).decode().strip().split()
    if parents != [commit]:
        raise ValueError('bootstrap commit must be parentless')
    tree=git('ls-tree','-z',commit)
    if tree.count(b'\x00') != 1:
        raise ValueError('root must have exactly one file')
    metadata,name=tree.rstrip(b'\x00').split(b'\t',1)
    if name!=b'state.json' or not metadata.startswith(b'100644 blob '):
        raise ValueError('unexpected root tree entry')
    raw=git('show',commit+':state.json')
    if raw != canonical(INITIAL_LEDGER):
        raise ValueError('bootstrap bytes mismatch')
    return {'schema_version':'rhombus-bootstrap-inspection-v1','root_sha':commit,
        'canonical_state_sha256':hashlib.sha256(raw).hexdigest(), 'structure':'PASS_OFFLINE',
        'owner_approval':'UNVERIFIED','branch_binding':'UNVERIFIED','effective_protection':'UNVERIFIED',
        'submission_authorization':False,'production_readiness':'NO_GO'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,required=True);p.add_argument('--root-sha',required=True)
    a=p.parse_args();print(json.dumps(inspect_root(a.repo,a.root_sha),sort_keys=True))

if __name__=='__main__':main()
