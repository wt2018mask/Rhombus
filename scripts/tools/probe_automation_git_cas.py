"""Real GitHub CAS probe on one uniquely named, retained test branch. No Kaggle."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import uuid

from rhombus.automation.ledger import GitHub, GitLedger, canonical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    token = subprocess.run(['gh', 'auth', 'token'], check=True, capture_output=True, text=True).stdout.strip()
    ledger = GitLedger(GitHub('wt2018mask/Rhombus', token))
    ledger.branch = 'rhombus-cas-probe-' + uuid.uuid4().hex
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(ledger.compare_and_swap, None,
            {'test_only': True, 'writer': index, 'science': 'NOT_EXECUTED'}) for index in range(2)]
        creation = [future.result() for future in futures]
    assert sum(value is not None for value in creation) == 1
    parent, _ = ledger.read()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(ledger.compare_and_swap, parent,
            {'test_only': True, 'writer': index, 'parent': parent, 'science': 'NOT_EXECUTED'}) for index in range(2)]
        updates = [future.result() for future in futures]
    assert sum(value is not None for value in updates) == 1
    final, _ = ledger.read()
    report = {'repository': 'wt2018mask/Rhombus', 'retained_probe_branch': ledger.branch,
              'creation_results': creation, 'sibling_update_results': updates,
              'final_commit': final, 'result': 'REAL_GITHUB_CAS_OBSERVED',
              'kaggle_submission': False, 'production_ledger_modified': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as output:
        output.write(canonical(report))
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
