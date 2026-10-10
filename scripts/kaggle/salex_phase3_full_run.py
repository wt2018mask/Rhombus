"""One-shot Kaggle CPU driver for the Phase 3 complete sAlex/WBM overlap run.

The GitHub control plane stages a private request dataset containing the exact
Rhombus commit and frozen source identities. This driver fails closed on any
identity drift, executes the complete one-pass production stream, and emits
chunked zstd outputs plus a hash-bound receipt for independent retrieval checks.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import BinaryIO

REQUEST_ROOT = Path("/kaggle/input")
# Filled only in the generated, exact-commit-bound Kaggle kernel source.
# It carries no credentials and is cross-checked against any attached dataset.
EMBEDDED_REQUEST_JSON: str | None = None
SCRATCH = Path("/kaggle/temp/rhombus-phase3-salex")
OUTPUT = Path("/kaggle/working")
REPO_URL = "https://github.com/wt2018mask/Rhombus.git"
MATBENCH_URL = "https://github.com/janosh/matbench-discovery.git"
CHUNK_SIZE = 128 * 1024 * 1024


def run(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True)


def output(*args: str, cwd: Path | None = None) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_request() -> tuple[Path | None, dict]:
    # Kaggle can mount the same dataset at /kaggle/input/<slug> or at a
    # deeper owner-qualified location. Never assume one directory depth.
    attached: list[tuple[Path, dict]] = []
    if REQUEST_ROOT.is_dir():
        for path in sorted(REQUEST_ROOT.rglob("request.json")):
            try:
                candidate = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"unreadable attached request: {path}") from exc
            if candidate.get("schema_version") == "rhombus-v2-salex-kaggle-full-run-request-v1":
                attached.append((path, candidate))
    if len(attached) > 1:
        raise RuntimeError(f"expected at most one Rhombus request dataset, found {[p for p, _ in attached]}")

    embedded = None
    if EMBEDDED_REQUEST_JSON is not None:
        embedded = json.loads(EMBEDDED_REQUEST_JSON)
        if embedded.get("schema_version") != "rhombus-v2-salex-kaggle-full-run-request-v1":
            raise RuntimeError("invalid embedded Rhombus request schema")
    if attached and embedded is not None and attached[0][1] != embedded:
        raise RuntimeError("Kaggle request dataset differs from exact-commit embedded request")
    if attached:
        path, request = attached[0]
    elif embedded is not None:
        path, request = None, embedded
    else:
        raise RuntimeError("Rhombus request missing from both Kaggle mounts and exact-commit kernel source")

    if request.get("enabled") is not True:
        raise RuntimeError("Kaggle production request is disabled")
    authorization = request.get("authorization", {})
    if authorization.get("full_run_authorized") is not True:
        raise RuntimeError("complete sAlex production run is not authorized")
    if authorization.get("unseen_generalization_claim") is not False:
        raise RuntimeError("sAlex run must not authorize unseen generalization")
    commit = request.get("source_commit")
    if not isinstance(commit, str) or len(commit) != 40 or any(
        char not in "0123456789abcdef" for char in commit
    ):
        raise RuntimeError("request lacks an exact 40-character Rhombus commit")
    return path, request


def checkout_exact(repository: str, destination: Path, commit: str) -> None:
    run("git", "init", "-q", str(destination))
    run("git", "-C", str(destination), "remote", "add", "origin", repository)
    run("git", "-C", str(destination), "fetch", "-q", "--depth=1", "origin", commit)
    run("git", "-C", str(destination), "checkout", "-q", "--detach", "FETCH_HEAD")
    observed = output("git", "-C", str(destination), "rev-parse", "HEAD")
    if observed != commit:
        raise RuntimeError(f"checkout drift: expected={commit} observed={observed}")


def verify_matbench_blobs(root: Path, expected: dict[str, str]) -> None:
    structure_root = root / "matbench_discovery" / "structure"
    for name, expected_blob in expected.items():
        path = structure_root / name
        if not path.is_file():
            raise RuntimeError(f"missing frozen Matbench file: {name}")
        observed = output("git", "-C", str(root), "hash-object", str(path))
        if observed != expected_blob:
            raise RuntimeError(
                f"Matbench blob drift file={name} expected={expected_blob} observed={observed}"
            )


def wbm_download_urls(primary_url: str) -> list[str]:
    """Return same-file public Figshare endpoints; never substitute another file."""
    prefix = "https://figshare.com/ndownloader/files/"
    if not primary_url.startswith(prefix):
        return [primary_url]
    file_id = primary_url[len(prefix):]
    if not file_id.isascii() or not file_id.isdecimal():
        return [primary_url]
    return [
        primary_url,
        f"https://api.figshare.com/v2/file/download/{file_id}",
        f"https://ndownloader.figshare.com/files/{file_id}",
    ]


def download_verified_wbm(source: dict, destination: Path) -> dict:
    """Fail closed on HTTP-successful but empty/corrupt downloads.

    The only admissible bytes are the exact SHA256-frozen WBM source.
    Each attempt is logged and diagnostic evidence is retained on total failure.
    """
    expected = source["sha256"]
    attempts = []
    destination.parent.mkdir(parents=True, exist_ok=True)
    for url in wbm_download_urls(source["url"]):
        destination.unlink(missing_ok=True)
        command = [
            "curl", "-L", "--fail", "--silent", "--show-error",
            "--retry", "2", "--retry-all-errors",
            "--connect-timeout", "30", "--max-time", "900",
            "--speed-limit", "10240", "--speed-time", "90",
            "--write-out", "%{http_code}",
            "--output", str(destination), url,
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        size = destination.stat().st_size if destination.is_file() else 0
        with destination.open("rb") if size else io.BytesIO() as handle:
            magic = handle.read(2)
        observed = sha256_file(destination) if size else None
        entry = {
            "url": url,
            "curl_exit_code": result.returncode,
            "http_status": result.stdout.strip()[-3:],
            "size_bytes": size,
            "gzip_magic_valid": magic == b"\x1f\x8b",
            "observed_sha256": observed,
            "sha256_valid": observed == expected,
            "stderr_excerpt": result.stderr[-250:],
        }
        attempts.append(entry)
        print("WBM_FROZEN_SOURCE_ATTEMPT " + json.dumps(entry, sort_keys=True), flush=True)
        if (
            result.returncode == 0
            and size > 0
            and magic == b"\x1f\x8b"
            and observed == expected
        ):
            return {
                "url": url,
                "sha256": observed,
                "size_bytes": size,
                "attempts": len(attempts),
            }
    destination.unlink(missing_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "rhombus_phase3_wbm_source_diagnostics.json").write_text(
        json.dumps({
            "status": "FROZEN_WBM_SOURCE_UNAVAILABLE",
            "expected_sha256": expected,
            "attempts": attempts,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    raise RuntimeError(
        "frozen WBM source unavailable from every same-file Figshare endpoint; "
        "scientific WBM target indexing and sAlex streaming were not started"
    )


class ChunkedWriter(io.RawIOBase):
    def __init__(self, root: Path, prefix: str, chunk_size: int = CHUNK_SIZE) -> None:
        super().__init__()
        self.root = root
        self.prefix = prefix
        self.chunk_size = chunk_size
        self.parts: list[dict[str, object]] = []
        self._handle: BinaryIO | None = None
        self._part_hash = hashlib.sha256()
        self._whole_hash = hashlib.sha256()
        self._part_size = 0
        self._part_index = 0

    def writable(self) -> bool:
        return True

    def _open_part(self) -> None:
        if self._handle is not None:
            return
        name = f"{self.prefix}.part{self._part_index:04d}"
        self._handle = (self.root / name).open("wb")
        self._part_hash = hashlib.sha256()
        self._part_size = 0

    def _finish_part(self) -> None:
        if self._handle is None:
            return
        self._handle.flush()
        self._handle.close()
        name = f"{self.prefix}.part{self._part_index:04d}"
        self.parts.append(
            {
                "name": name,
                "size_bytes": self._part_size,
                "sha256": self._part_hash.hexdigest(),
            }
        )
        self._handle = None
        self._part_index += 1
        self._part_size = 0

    def write(self, data: bytes | bytearray) -> int:
        view = memoryview(data)
        total = len(view)
        while view:
            self._open_part()
            assert self._handle is not None
            room = self.chunk_size - self._part_size
            piece = view[:room]
            self._handle.write(piece)
            self._part_hash.update(piece)
            self._whole_hash.update(piece)
            count = len(piece)
            self._part_size += count
            view = view[count:]
            if self._part_size == self.chunk_size:
                self._finish_part()
        return total

    def flush(self) -> None:
        if self._handle is not None:
            self._handle.flush()

    def finalize(self) -> tuple[list[dict[str, object]], str]:
        self._finish_part()
        return self.parts, self._whole_hash.hexdigest()


def compress_chunked(source: Path, prefix: str) -> tuple[list[dict[str, object]], str]:
    import zstandard as zstd

    writer = ChunkedWriter(OUTPUT, prefix)
    compressor = zstd.ZstdCompressor(level=6, threads=0)
    with source.open("rb") as handle:
        with compressor.stream_writer(writer, closefd=False) as sink:
            shutil.copyfileobj(handle, sink, length=8 * 1024 * 1024)
    return writer.finalize()


def main() -> None:
    started_at = utc_now()
    request_path, request = find_request()
    source_commit = request["source_commit"]
    sources = request["frozen_sources"]

    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    repo_root = SCRATCH / "Rhombus"
    checkout_exact(REPO_URL, repo_root, source_commit)

    matbench = sources["prototype_protocol"]
    matbench_root = SCRATCH / "matbench-discovery"
    checkout_exact(MATBENCH_URL, matbench_root, matbench["commit"])
    verify_matbench_blobs(matbench_root, matbench["git_blobs"])

    # Validate external WBM bytes before expensive dependency installation.
    # A successful curl exit code alone does not prove any bytes were returned.
    wbm = sources["wbm_initial_structures"]
    wbm_path = SCRATCH / "wbm-init.jsonl.gz"
    wbm_retrieval = download_verified_wbm(wbm, wbm_path)
    observed_wbm_sha = wbm_retrieval["sha256"]

    constraints = repo_root / "scripts" / "ci" / "constraints.txt"
    run(
        sys.executable,
        "-m",
        "pip",
        "install",
        "-q",
        "-c",
        str(constraints),
        "numpy",
        "pyyaml",
        "pymatgen",
        "ase",
        "ase-db-backends",
        "moyopy==0.3.4",
        "zstandard==0.25.0",
    )
    run(sys.executable, "-m", "pip", "install", "--no-deps", "-e", str(repo_root))
    from rhombus.evidence.runtime_provenance import collect_runtime_provenance

    target_db = SCRATCH / "wbm-targets.sqlite"
    membership_db = SCRATCH / "salex-membership.sqlite"
    overlap_jsonl = SCRATCH / "wbm-salex-overlap.jsonl"
    summary_json = SCRATCH / "summary.json"

    env = dict(os.environ)
    env["RHOMBUS_MATBENCH_PROTOCOL_SOURCE_DIR"] = str(
        matbench_root / "matbench_discovery" / "structure"
    )
    run(
        sys.executable,
        str(repo_root / "scripts" / "development" / "run_salex_wbm_overlap.py"),
        "full",
        "--wbm-path",
        str(wbm_path),
        "--target-db",
        str(target_db),
        "--membership-db",
        str(membership_db),
        "--overlap-jsonl",
        str(overlap_jsonl),
        "--summary-json",
        str(summary_json),
        "--partial-output-dir",
        str(OUTPUT / "rhombus_salex_partial_chunks"),
        env=env,
    )

    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    salex = sources["salex"]
    if summary["salex_source_sha256"] != salex["sha256"]:
        raise RuntimeError("complete sAlex source SHA256 was not verified")
    if summary["salex_membership_row_count"] != salex["expected_records"]:
        raise RuntimeError("complete sAlex row count was not verified")
    if summary["wbm_source_sha256"] != wbm["sha256"]:
        raise RuntimeError("summary WBM source SHA256 mismatch")
    if summary["wbm_target_count"] != wbm["expected_records"]:
        raise RuntimeError("summary WBM target count mismatch")
    if summary["unseen_generalization_claim_authorized"] is not False:
        raise RuntimeError("sAlex-only result widened unseen-generalization authority")

    summary_out = OUTPUT / "rhombus_phase3_salex_summary.json"
    shutil.copy2(summary_json, summary_out)

    membership_parts, membership_compressed_sha = compress_chunked(
        membership_db,
        "rhombus_phase3_salex_membership.sqlite.zst",
    )
    overlap_parts, overlap_compressed_sha = compress_chunked(
        overlap_jsonl,
        "rhombus_phase3_wbm_salex_overlap.jsonl.zst",
    )

    receipt = {
        "schema_version": "rhombus-v2-salex-kaggle-run-receipt-v1",
        "status": "PRODUCTION_COMPLETE_SOURCE_STREAM_FINISHED",
        "source_commit": source_commit,
        "runtime_provenance": collect_runtime_provenance(repo_root),
        "request_dataset_path": str(request_path) if request_path is not None else None,
        "request_delivery": (
            "MOUNTED_KAGGLE_DATASET"
            if request_path is not None
            else "EXACT_COMMIT_EMBEDDED_KERNEL_REQUEST"
        ),
        "started_at": started_at,
        "finished_at": utc_now(),
        "frozen_sources": sources,
        "verified": {
            "rhombus_commit": source_commit,
            "matbench_commit": matbench["commit"],
            "matbench_git_blobs": matbench["git_blobs"],
            "wbm_source_sha256": observed_wbm_sha,
            "wbm_download": wbm_retrieval,
            "wbm_target_count": summary["wbm_target_count"],
            "salex_source_sha256": summary["salex_source_sha256"],
            "salex_membership_row_count": summary["salex_membership_row_count"],
        },
        "summary": {
            "name": summary_out.name,
            "sha256": sha256_file(summary_out),
        },
        "membership_archive": {
            "compression": "zstd-level-6-single-frame-split-128MiB",
            "raw_sha256": summary["membership_index_sha256"],
            "compressed_sha256": membership_compressed_sha,
            "parts": membership_parts,
        },
        "overlap_archive": {
            "compression": "zstd-level-6-single-frame-split-128MiB",
            "raw_sha256": summary["overlap_jsonl_sha256"],
            "compressed_sha256": overlap_compressed_sha,
            "parts": overlap_parts,
        },
        "scientific_authorization": {
            "salex_component_audit_completed": True,
            "full_training_lineage_resolved": False,
            "unseen_generalization_claim_authorized": False,
            "remaining_blocker": "MPTRJ_TRAINING_REPRESENTATION_UNATTESTED",
        },
    }
    receipt_path = OUTPUT / "rhombus_phase3_salex_run_receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "RHOMBUS_PHASE3_SALEX_KAGGLE_COMPLETE",
        source_commit,
        summary["salex_membership_row_count"],
    )


if __name__ == "__main__":
    main()
