"""Official Kaggle 2.2.5 adapter; no raw provider messages leave this module."""
from __future__ import annotations

from contextlib import contextmanager, redirect_stdout, redirect_stderr
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from rhombus.automation.ledger import ControlError, canonical


class KaggleProvider:
    def __init__(self, username):
        self.username = username
        self.api = None

    def authenticate(self):
        if not os.environ.get("KAGGLE_API_TOKEN"):
            raise ControlError("AUTHENTICATION_NOT_CONFIGURED")
        if importlib.metadata.version("kaggle") != "2.2.5" or importlib.metadata.version("kagglesdk") != "0.1.38":
            raise ControlError("UNSUPPORTED_KAGGLE_CLIENT")
        try:
            with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
                from kaggle.api.kaggle_api_extended import KaggleApi
                self.api = KaggleApi()
                self.api.build_kaggle_client = self.client
                if not self.api._authenticate_with_access_token():
                    raise ControlError("AUTHENTICATION_FAILED")
                if self.api.config_values.get("username") != self.username:
                    raise ControlError("AUTHENTICATED_ACCOUNT_MISMATCH")
                self.api.kernels_list(mine=True, page_size=1)
        except (Exception, SystemExit):
            raise ControlError("AUTHENTICATION_FAILED") from None
        return {"authentication": "AUTHENTICATED_READ_ONLY", "username": self.username,
                "free_cpu_eligibility": "NOT_EXPOSED_BY_READ_ONLY_API",
                "remaining_cpu_quota": "UNKNOWN", "resource_request": "DEFAULT_CPU_NO_PAID_SHAPE",
                "gpu": "DISABLED_BY_POLICY"}

    @contextmanager
    def client(self, *args, **kwargs):
        from kagglesdk import KaggleClient, KaggleEnv
        with KaggleClient(api_token=os.environ["KAGGLE_API_TOKEN"], env=KaggleEnv.PROD, verbose=False) as client:
            session = client._http_client._session
            original = session.send
            def bounded_send(request, **options):
                options.update(timeout=(15, 60), allow_redirects=False)
                response = original(request, **options)
                if 300 <= response.status_code < 400:
                    raise ControlError("PROVIDER_REDIRECT_DENIED")
                return response
            session.send = bounded_send
            yield client

    def prepare(self, staging, request, identity):
        staging = Path(staging)
        staging.mkdir(parents=True, exist_ok=False)
        template = Path(__file__).with_name("worker.py").read_text(encoding="utf-8")
        source = "REQUEST = " + repr(request) + "\nPROVIDER_RUN_ID = " + repr(identity + "/1") + "\n" + template
        (staging / "kernel.py").write_bytes(source.encode())
        (staging / "kernel-metadata.json").write_bytes(canonical({
            "id": identity, "title": identity.split("/")[1], "code_file": "kernel.py",
            "language": "python", "kernel_type": "script", "is_private": True,
            "enable_gpu": False, "enable_tpu": False, "enable_internet": True,
            "dataset_sources": [], "competition_sources": [], "kernel_sources": [], "model_sources": []}))

    def ensure_absent(self, identity):
        import requests
        from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
        request = ApiGetKernelRequest()
        request.user_name, request.kernel_slug = identity.split('/')
        try:
            with self.client() as client:
                client.kernels.kernels_api_client.get_kernel(request)
        except requests.HTTPError as error:
            if error.response is not None and error.response.status_code == 404:
                return
            raise ControlError('PROVIDER_IDENTITY_ABSENCE_UNCERTAIN') from None
        raise ControlError('PROVIDER_IDENTITY_ALREADY_EXISTS')

    def submit(self, staging, identity, wall_seconds):
        response = self.api.kernels_push(str(staging), timeout=str(wall_seconds), no_run=False)
        if response.error or response.ref != identity or response.version_number != 1:
            raise ControlError("SUBMISSION_OUTCOME_UNCERTAIN")
        return {"provider_identity": response.ref, "version": response.version_number,
                "kernel_id": response.kernel_id, "status": "ACCEPTED"}

    def observe(self, run_id, script_sha256):
        from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
        owner, slug, version = run_id.split("/")
        request = ApiGetKernelRequest()
        request.user_name, request.kernel_slug, request.version_label = owner, slug, "v" + version
        with self.client() as client:
            response = client.kernels.kernels_api_client.get_kernel(request)
        metadata = response.metadata
        if (metadata.ref != owner + "/" + slug or not metadata.is_private
                or metadata.enable_gpu or metadata.enable_tpu
                or metadata.current_version_number != 1
                or hashlib.sha256(response.blob.source.encode()).hexdigest() != script_sha256):
            raise ControlError("PROVIDER_SOURCE_OR_VERSION_MISMATCH")
        status = self.api.kernels_status(run_id).status.name
        state = {"QUEUED": "ACCEPTED", "RUNNING": "RUNNING", "COMPLETE": "COMPLETE",
                 "ERROR": "ERROR", "CANCEL_ACKNOWLEDGED": "ERROR"}.get(status, "UNKNOWN")
        return {"state": state, "provider_status": status, "version": 1,
                "source_sha256": script_sha256, "machine_shape": metadata.machine_shape,
                "origin_binding": "AUTHENTICATED_VERSION_SOURCE_AND_OUTPUT_API_NOT_RUNTIME_ATTESTATION"}

    def retrieve(self, run_id, destination, budget):
        from kagglesdk.kernels.types.kernels_api_service import ApiListKernelSessionOutputRequest
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=False)
        owner, slug, version = run_id.split("/")
        request = ApiListKernelSessionOutputRequest()
        request.user_name, request.kernel_slug, request.version_label = owner, slug, "v" + version
        request.page_size = 100
        with self.client() as client:
            response = client.kernels.kernels_api_client.list_kernel_session_output(request)
        if response.next_page_token or len(response.files) > 100:
            raise ControlError("OUTPUT_INVENTORY_BUDGET")
        selected = [item for item in response.files if item.file_name.startswith("result/")]
        names = set()
        remaining = budget
        for item in selected:
            name = item.file_name.removeprefix("result/")
            if not re.fullmatch(r"[a-zA-Z0-9_.-]+", name) or name in (".", "..") or name in names:
                raise ControlError("UNSAFE_OUTPUT_PATH")
            names.add(name)
            remaining -= download(item.url, destination / name, remaining)
        log = response.log.encode()
        if len(log) > 1048576:
            log = log[-1048576:]
        (destination.parent / "provider.log").write_bytes(log)
        execution = [item for item in response.files if item.file_name == "execution.log"]
        if len(execution) > 1:
            raise ControlError("DUPLICATE_EXECUTION_LOG")
        if execution:
            download(execution[0].url, destination.parent / "execution.log", 1048576)
        return {"provider_run_id": run_id, "retrieval": "AUTHENTICATED_VERSION_OUTPUT_LIST",
                "files": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in destination.iterdir()},
                "log_sha256": hashlib.sha256(log).hexdigest()}


def download(url, target, limit):
    import requests
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443)
            or not (host == "storage.googleapis.com" or host.endswith(".googleusercontent.com"))):
        raise ControlError("OUTPUT_DOWNLOAD_ORIGIN_DENIED")
    total = 0
    with requests.Session() as session:
        session.trust_env = False
        with session.get(url, stream=True, timeout=(15, 60), allow_redirects=False) as response:
            if response.status_code != 200:
                raise ControlError("OUTPUT_DOWNLOAD_FAILED")
            if int(response.headers.get("Content-Length", "0")) > limit:
                raise ControlError("OUTPUT_SIZE_BUDGET")
            with Path(target).open("xb") as output:
                for chunk in response.iter_content(65536):
                    total += len(chunk)
                    if total > limit:
                        raise ControlError("OUTPUT_SIZE_BUDGET")
                    output.write(chunk)
            expected = int(response.headers.get('Content-Length', '0'))
            if expected and total != expected:
                raise ControlError('PARTIAL_OUTPUT_DOWNLOAD')
    return total
