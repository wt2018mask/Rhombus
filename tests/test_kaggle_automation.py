"""Adversarial control tests. Fixtures never represent an actual provider run."""
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import threading
from unittest.mock import Mock

import pytest

from rhombus.automation.controller import build_request, reconcile, validate_policy
from rhombus.automation.kaggle import KaggleProvider, download
from rhombus.automation.ledger import ControlError, GitLedger, canonical, digest

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / 'rhombus/automation/policy.json').read_bytes())


class MemoryLedger:
    def __init__(self):
        self.revision = None
        self.state = None
        self.lock = threading.Lock()
        self.lose_response = False

    def read(self):
        with self.lock:
            return self.revision, copy.deepcopy(self.state)

    def compare_and_swap(self, previous, state):
        with self.lock:
            if previous != self.revision:
                return None
            self.revision = digest({'parent': previous, 'state': state})
            self.state = copy.deepcopy(state)
            if self.lose_response:
                self.lose_response = False
                raise ControlError('GITHUB_OUTCOME_UNCERTAIN')
            return self.revision


class FakeProvider:
    def __init__(self):
        self.submissions = 0
        self.failure = None
        self.observed = 'RUNNING'
        self.barrier = None

    def authenticate(self):
        return {'username': 'synthetic'}

    def ensure_absent(self, identity):
        pass

    def prepare(self, staging, request, identity):
        KaggleProvider('synthetic').prepare(staging, request, identity)
        if self.barrier:
            self.barrier.wait(timeout=10)

    def submit(self, staging, identity, wall_seconds):
        self.submissions += 1
        if self.failure:
            raise self.failure
        return {'provider_identity': identity, 'version': 1, 'status': 'ACCEPTED'}

    def observe(self, run_id, checksum):
        if isinstance(self.observed, Exception):
            raise self.observed
        return {'state': self.observed, 'origin_binding': 'SYNTHETIC_NOT_KAGGLE'}


def tick(ledger, provider, path):
    return reconcile(ledger, provider, POLICY, build_request(), digest(POLICY), path)


def test_simultaneous_controllers_submit_once(tmp_path):
    ledger, provider = MemoryLedger(), FakeProvider()
    provider.barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(tick, ledger, provider, tmp_path / str(index)) for index in range(2)]
        outcomes = [future.result() for future in futures]
    assert provider.submissions == 1
    assert {row['state'] for row in outcomes} == {'ACCEPTED', 'CLAIM_LOST_NO_SUBMISSION'}
    for index in range(5):
        tick(ledger, provider, tmp_path / ('restart' + str(index)))
    assert provider.submissions == 1


@pytest.mark.parametrize('failure', [TimeoutError('SECRET'), ConnectionError('SECRET')])
def test_acceptance_uncertainty_is_never_retried(tmp_path, failure):
    ledger, provider = MemoryLedger(), FakeProvider()
    provider.failure = failure
    assert tick(ledger, provider, tmp_path / 'initial')['state'] == 'SUBMISSION_OUTCOME_UNCERTAIN'
    provider.observed = ConnectionError('SECRET')
    for index in range(3):
        assert tick(ledger, provider, tmp_path / str(index))['state'] == 'SUBMISSION_OUTCOME_UNCERTAIN'
    provider.observed = 'COMPLETE'
    assert tick(ledger, provider, tmp_path / 'recovered')['state'] == 'COMPLETE'
    assert provider.submissions == 1
    assert 'SECRET' not in canonical(ledger.state).decode()


def test_lost_claim_response_never_authorizes_submit(tmp_path):
    ledger, provider = MemoryLedger(), FakeProvider()
    ledger.lose_response = True
    with pytest.raises(ControlError):
        tick(ledger, provider, tmp_path / 'initial')
    assert ledger.state['state'] == 'SUBMISSION_PENDING'
    provider.observed = ConnectionError()
    tick(ledger, provider, tmp_path / 'restart')
    assert provider.submissions == 0


def test_cancel_after_claim_and_before_receipt(tmp_path):
    ledger, provider = MemoryLedger(), FakeProvider()
    provider.failure = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        tick(ledger, provider, tmp_path / 'initial')
    tick(ledger, provider, tmp_path / 'restart')
    assert provider.submissions == 1


def test_failure_before_claim_does_not_consume(tmp_path):
    ledger, provider = MemoryLedger(), FakeProvider()
    provider.authenticate = Mock(side_effect=ControlError('AUTHENTICATION_FAILED'))
    with pytest.raises(ControlError):
        tick(ledger, provider, tmp_path)
    assert ledger.read() == (None, None)
    assert provider.submissions == 0


def test_stale_status_does_not_regress_completed(tmp_path):
    ledger, provider = MemoryLedger(), FakeProvider()
    tick(ledger, provider, tmp_path / 'initial')
    provider.observed = 'COMPLETE'
    tick(ledger, provider, tmp_path / 'complete')
    provider.observed = 'RUNNING'
    assert tick(ledger, provider, tmp_path / 'stale')['state'] == 'COMPLETE'


@pytest.mark.parametrize('field,value', [('gpu_enabled', True), ('max_submissions', 2), ('money_usd', 1), ('source_commit', 'a' * 40)])
def test_policy_revision_cannot_expand_supported_authority(field, value):
    policy = dict(POLICY, **{field: value})
    with pytest.raises(ControlError):
        validate_policy(policy, build_request(), digest(policy))


def test_ai_request_cannot_authorize_itself():
    with pytest.raises(ControlError):
        validate_policy(POLICY, build_request(), None)
    request = build_request()
    request['protocol']['study']['temperature_K'] = 999
    with pytest.raises(ControlError):
        validate_policy(POLICY, request, digest(POLICY))


def test_missing_token_does_not_import_or_call_provider(monkeypatch):
    monkeypatch.delenv('KAGGLE_API_TOKEN', raising=False)
    with pytest.raises(ControlError, match='AUTHENTICATION_NOT_CONFIGURED'):
        KaggleProvider('synthetic').authenticate()


def test_worker_has_exact_request_and_no_secret(tmp_path, monkeypatch):
    monkeypatch.setenv('KAGGLE_API_TOKEN', 'NEVER_EMBED_THIS')
    provider = KaggleProvider('synthetic')
    provider.prepare(tmp_path / 'stage', build_request(), 'synthetic/rhombus-fixed')
    code = (tmp_path / 'stage/kernel.py').read_text()
    compile(code, '<kaggle-worker>', 'exec')
    assert 'NEVER_EMBED_THIS' not in code
    metadata = json.loads((tmp_path / 'stage/kernel-metadata.json').read_bytes())
    assert metadata['is_private'] is True and metadata['enable_gpu'] is False and metadata['enable_tpu'] is False


@pytest.mark.parametrize('url', ['http://storage.googleapis.com/a', 'https://evil.example/a', 'https://storage.googleapis.com.evil.example/a', 'https://user:pass@storage.googleapis.com/a'])
def test_signed_download_origin_is_restricted(tmp_path, url):
    with pytest.raises(ControlError):
        download(url, tmp_path / 'output', 1024)
    assert not (tmp_path / 'output').exists()


def test_git_cas_uses_non_force_and_observed_parent():
    github = Mock()
    github.call.side_effect = [{'sha': 'tree'}, {'sha': 'commit'}, {'object': {'sha': 'commit'}}]
    assert GitLedger(github).compare_and_swap('parent', {'state': 'test'}) == 'commit'
    assert github.call.call_args_list[1].args[2]['parents'] == ['parent']
    assert github.call.call_args_list[2].args[2] == {'sha': 'commit', 'force': False}


def test_git_claim_conflict_returns_no_authority():
    github = Mock()
    github.call.side_effect = [{'sha': 'tree'}, {'sha': 'commit'}, None]
    assert GitLedger(github).compare_and_swap(None, {'state': 'test'}) is None


def test_checked_sdk_has_one_send_without_retry():
    import inspect
    from kagglesdk.kaggle_http_client import KaggleHttpClient
    source = inspect.getsource(KaggleHttpClient.call)
    assert source.count('self._session.send(') == 1
    assert 'retry' not in source


def test_workflow_never_runs_privileged_pr_code():
    source = (ROOT / '.github/workflows/kaggle-thermal-controller.yml').read_text()
    assert 'pull_request' not in source
    assert "github.ref == 'refs/heads/main'" in source
    assert 'environment: kaggle-production' in source
    assert 'KAGGLE_API_TOKEN: ${{ secrets.KAGGLE_API_TOKEN }}' in source
    assert 'KAGGLE_USERNAME: ${{ vars.KAGGLE_USERNAME || secrets.KAGGLE_USERNAME }}' in source
    assert 'persist-credentials: false' in source
    assert '474df8faa7484b87f19e5679336192939598e1f7' in source


def test_invalid_token_cannot_fall_back_to_legacy(monkeypatch, capsys):
    monkeypatch.delenv('KAGGLE_API_TOKEN', raising=False)
    from kaggle.api.kaggle_api_extended import KaggleApi
    capsys.readouterr()
    monkeypatch.setenv('KAGGLE_API_TOKEN', 'INVALID_TOKEN_MUST_NOT_LEAK')
    monkeypatch.setattr(KaggleApi, '_authenticate_with_access_token', lambda self: False)
    legacy = Mock(side_effect=AssertionError('legacy fallback forbidden'))
    monkeypatch.setattr(KaggleApi, '_authenticate_with_legacy_apikey', legacy)
    with pytest.raises(ControlError, match='AUTHENTICATION_FAILED'):
        KaggleProvider('synthetic').authenticate()
    assert not legacy.called
    captured = capsys.readouterr()
    assert 'INVALID_TOKEN' not in captured.out + captured.err


def test_official_sdk_version_specific_status_and_source(monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from kagglesdk.kernels.types.kernels_enums import KernelWorkerStatus
    provider = KaggleProvider('synthetic')
    source = 'print("synthetic")\n'
    metadata = SimpleNamespace(ref='synthetic/example', is_private=True, enable_gpu=False,
        enable_tpu=False, current_version_number=1, machine_shape='synthetic-cpu')
    get_kernel = Mock(return_value=SimpleNamespace(metadata=metadata, blob=SimpleNamespace(source=source)))
    @contextmanager
    def client():
        yield SimpleNamespace(kernels=SimpleNamespace(kernels_api_client=SimpleNamespace(get_kernel=get_kernel)))
    monkeypatch.setattr(provider, 'client', client)
    provider.api = Mock()
    provider.api.kernels_status.return_value = SimpleNamespace(status=KernelWorkerStatus.COMPLETE)
    assert provider.observe('synthetic/example/1', hashlib.sha256(source.encode()).hexdigest())['state'] == 'COMPLETE'
    assert get_kernel.call_args.args[0].version_label == 'v1'
    provider.api.kernels_status.assert_called_once_with('synthetic/example/1')
    metadata.current_version_number = 2
    with pytest.raises(ControlError):
        provider.observe('synthetic/example/1', hashlib.sha256(source.encode()).hexdigest())


def test_submission_response_loss_and_wrong_version_are_uncertain(tmp_path):
    from types import SimpleNamespace
    provider = KaggleProvider('synthetic')
    provider.api = Mock()
    provider.api.kernels_push.return_value = SimpleNamespace(error='', ref='synthetic/example', version_number=2)
    with pytest.raises(ControlError, match='SUBMISSION_OUTCOME_UNCERTAIN'):
        provider.submit(tmp_path, 'synthetic/example', 10800)
    provider.api.kernels_push.assert_called_once_with(str(tmp_path), timeout='10800', no_run=False)


def test_interrupted_download_and_oversize_are_detected(tmp_path, monkeypatch):
    import requests
    response = Mock()
    response.status_code = 200
    response.headers = {'Content-Length': '10'}
    response.iter_content.return_value = iter([b'abc'])
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    session = Mock()
    session.get.return_value = response
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(requests, 'Session', lambda: session)
    with pytest.raises(ControlError, match='PARTIAL_OUTPUT_DOWNLOAD'):
        download('https://storage.googleapis.com/test', tmp_path / 'partial', 100)
    assert (tmp_path / 'partial').read_bytes() == b'abc'
    assert session.trust_env is False
    assert session.get.call_args.kwargs['allow_redirects'] is False
    with pytest.raises(ControlError, match='OUTPUT_SIZE_BUDGET'):
        download('https://storage.googleapis.com/test', tmp_path / 'too-large', 5)
    assert not (tmp_path / 'too-large').exists()


def test_automation_mcp_tools_have_strict_schema_and_dispatch_only_main(tmp_path):
    import asyncio
    from rhombus.automation.mcp_server import create_server
    github = Mock()
    github.call.return_value = {}
    server = create_server(tmp_path / 'evidence.jsonl', github)
    async def inspect():
        tools = await server.list_tools()
        assert len(tools) == 8
        extra = next(tool for tool in tools if tool.name == 'request_approved_thermal_study')
        assert extra.input_schema['additionalProperties'] is False
        with pytest.raises(Exception):
            await server.call_tool('request_approved_thermal_study', {'code': 'evil'})
        assert not github.call.called
        await server.call_tool('request_approved_thermal_study', {})
        github.call.assert_called_once_with('POST', '/actions/workflows/kaggle-thermal-controller.yml/dispatches',
            {'ref': 'main', 'inputs': {'operation': 'reconcile'}})
    asyncio.run(inspect())
