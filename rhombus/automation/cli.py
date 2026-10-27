"""Trusted controller entry point. Scientific verification runs without secrets."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from rhombus.automation.controller import SOURCE, build_request, reconcile, validate_policy
from rhombus.automation.kaggle import KaggleProvider
from rhombus.automation.ledger import ControlError, GitHub, GitLedger, canonical, digest


def require_ledger_protection(github, branch):
    protection = github.call('GET', '/branches/' + branch + '/protection')
    if (protection.get('allow_force_pushes', {}).get('enabled') is not False
            or protection.get('allow_deletions', {}).get('enabled') is not False
            or protection.get('enforce_admins', {}).get('enabled') is not True):
        raise ControlError('LEDGER_BRANCH_PROTECTION_REQUIRED')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('policy-digest', 'preflight', 'reconcile', 'verify', 'publish'))
    parser.add_argument('--output', type=Path, default=Path('automation-output'))
    parser.add_argument('--science-root', type=Path)
    args = parser.parse_args(argv)
    policy = json.loads(Path(__file__).with_name('policy.json').read_bytes())
    if args.action == 'policy-digest':
        print(digest(policy))
        return
    request = build_request()
    if args.action == 'verify':
        if any(os.environ.get(name) for name in ('KAGGLE_API_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN')):
            raise ControlError('VERIFIER_MUST_BE_UNPRIVILEGED')
        if args.science_root:
            import rhombus
            root = args.science_root.resolve()
            rhombus.__path__.insert(0, str(root / 'rhombus'))
            sys.path.insert(0, str(root))
        from rhombus.automation.verify import verify_results
        state = json.loads((args.output / 'state.json').read_bytes())
        retrieval = json.loads((args.output / 'retrieval.json').read_bytes())
        try:
            report = verify_results(args.output / 'result', request, state, retrieval)
        except Exception:
            report = {'state': 'SCIENTIFIC_VERIFICATION_FAILED', 'evidence_records': [],
                      'qualification': 'ABSTAIN', 'conductivity_S_cm': None}
        (args.output / 'verification.json').write_bytes(canonical(report))
        (args.output / 'evidence.jsonl').write_bytes(b''.join(canonical(row) for row in report['evidence_records']))
        print(report['state'])
        return
    if (os.environ.get('GITHUB_REPOSITORY') != 'wt2018mask/Rhombus'
            or os.environ.get('GITHUB_REF') != 'refs/heads/main'
            or os.environ.get('GITHUB_EVENT_NAME') not in ('schedule', 'workflow_dispatch')):
        raise ControlError('TRUSTED_DEFAULT_BRANCH_REQUIRED')
    approved = os.environ.get('RHOMBUS_POLICY_SHA256')
    validate_policy(policy, request, approved)
    github = GitHub('wt2018mask/Rhombus', os.environ.get('GH_TOKEN'))
    environment = github.call('GET', '/environments/kaggle-production')
    branches = github.call('GET', '/environments/kaggle-production/deployment-branch-policies')
    if (environment.get('deployment_branch_policy') != {'protected_branches': False, 'custom_branch_policies': True}
            or branches.get('total_count') != 1
            or [(row.get('name'), row.get('type')) for row in branches.get('branch_policies', [])] != [('main', 'branch')]):
        raise ControlError('TRUSTED_ENVIRONMENT_BRANCH_RESTRICTION_REQUIRED')
    provider = KaggleProvider(os.environ.get('KAGGLE_USERNAME', ''))
    if args.action == 'preflight':
        print(json.dumps(provider.authenticate(), sort_keys=True))
        return
    ledger = GitLedger(github)
    # The one-shot CAS guarantee relies on this ref not being deleted or
    # force-updated, including by administrators. Fail closed before either
    # submission or publication if that protection cannot be observed.
    require_ledger_protection(github, ledger.branch)
    if args.action == 'publish':
        from rhombus.automation.archive import archive_results
        report = json.loads((args.output / 'verification.json').read_bytes())
        saved = json.loads((args.output / 'state.json').read_bytes())
        revision, current = ledger.read()
        if current != saved or current['request_sha256'] != digest(request):
            raise ControlError('ARCHIVE_STATE_CHANGED')
        archive = archive_results(args.output, 'wt2018mask/Rhombus', SOURCE, request['task_id'])
        current.update(state=report['state'], archive=archive, evidence_records=report['evidence_records'])
        if ledger.compare_and_swap(revision, current) is None:
            raise ControlError('ARCHIVED_STATE_CONFLICT')
        print(current['state'])
        return
    args.output.mkdir(parents=True, exist_ok=False)
    state = reconcile(ledger, provider, policy, request, approved, args.output / 'staging')
    print(state['state'])
    if state['state'] not in ('COMPLETE', 'ERROR', 'RETRIEVAL_PENDING'):
        return
    revision, current = ledger.read()
    if current != state:
        raise ControlError('RETRIEVAL_STATE_CHANGED')
    state['state'] = 'RETRIEVAL_PENDING'
    if ledger.compare_and_swap(revision, state) is None:
        raise ControlError('RETRIEVAL_STATE_CONFLICT')
    (args.output / 'state.json').write_bytes(canonical(state))
    (args.output / 'request.json').write_bytes(canonical(request))
    retrieval = provider.retrieve(state['provider_run_id'], args.output / 'result', policy['output_bytes'])
    provider.observe(state['provider_run_id'], state['script_sha256'])
    (args.output / 'retrieval.json').write_bytes(canonical(retrieval))


if __name__ == '__main__':
    try:
        main()
    except ControlError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except (Exception, SystemExit) as error:
        if isinstance(error, SystemExit):
            raise
        print('CONTROLLER_FAILED_CLOSED', file=sys.stderr)
        sys.exit(1)
