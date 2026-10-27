"""Read-only offline readiness report; does not probe or authorize providers."""
import json
from pathlib import Path
from rhombus.automation.controller import build_request, validate_policy
from rhombus.automation.ledger import digest


def main():
    policy=json.loads((Path(__file__).resolve().parents[2]/'rhombus/automation/policy.json').read_bytes())
    expected='921f430a7e2435c763760f9ac866306c15ac7dc14572353ca76b4a2d682a1ea2'
    validate_policy(policy,build_request(),expected)
    print(json.dumps({'schema_version':'rhombus-0203-offline-readiness-v1',
        'READY_OFFLINE':'POLICY_AND_REQUEST_INTEGRITY_VERIFIED_ONLY',
        'BLOCKED_ADMIN_CONFIGURATION':'REQUIRES_INDEPENDENT_PRODUCTION_OBSERVATION',
        'BLOCKED_CREDENTIAL_VERIFICATION':'UNVERIFIED',
        'BLOCKED_LEDGER_PROTECTION':'UNVERIFIED',
        'BLOCKED_DEPLOYMENT':'NOT_DEPLOYED',
        'BLOCKED_PROVIDER_PREFLIGHT':'NOT_EXECUTED',
        'REMOTE_SCIENCE_NOT_EXECUTED':True, 'policy_sha256':digest(policy),
        'production_readiness':'NO_GO'},sort_keys=True))

if __name__=='__main__':main()
