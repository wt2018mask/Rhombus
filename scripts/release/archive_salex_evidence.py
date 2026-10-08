#!/usr/bin/env python3
"""Safely archive the original frozen sAlex outputs into a DRAFT GitHub Release.

Never publishes, overwrites release assets, deletes data, submits Kaggle jobs,
or treats a missing original execution receipt as complete scientific attestation.
Requires the seven original files already downloaded by the operator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = "wt2018mask/Rhombus"
SOURCE_COMMIT = "643b8a260b6fcff78bb02f3a63f348c29fd91317"
TAG = "phase3-salex-643b8a260b6f-evidence-v1"
CANONICAL_DRAFT_RELEASE_ID = 406879217  # first created draft; never target another ID
TITLE = "Rhombus Phase 3 sAlex — preserved evidence (REVIEW REQUIRED)"
SUMMARY_NAME = "rhombus_phase3_salex_summary.json"
MANIFEST_NAME = "phase3_salex_preserved_local_evidence_v1.json"
MAX_RELEASE_ASSET = 2 * 1024**3
EXPECTED_PARTS = [
    f"rhombus_phase3_salex_membership.sqlite.zst.part{i:04d}" for i in range(5)
] + ["rhombus_phase3_wbm_salex_overlap.jsonl.zst.part0000"]
EXPECTED_SOURCE_DIGESTS = {
    "membership": "52aaf76fd1f8d637399323e57eafa885870bb6f5009664dcbc01dd1d07131b33",
    "overlap": "5f9e0644ea1eb48ad661b2a62abe88269c962ab9af0daf7e0936c9925290bb44",
}
EXPECTED_SUMMARY_DIGEST = "f9928681ebf347de77a99611ae45fa75f34367204206bac7551be4149d0fdcad"
MANIFEST_DEFAULT = (
    Path(__file__).resolve().parents[2]
    / "data/development/phase3_salex_preserved_local_evidence_v1.json"
)


class ArchivalError(RuntimeError):
    """Clear fail-closed archival error without leaking API outputs."""


def digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as reader:
        for chunk in iter(lambda: reader.read(8 * 1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def check_file(path: Path, size: int, digest: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ArchivalError(f"missing or unsafe file: {path.name}")
    if path.stat().st_size != size:
        raise ArchivalError(f"byte-size mismatch: {path.name}")
    if size >= MAX_RELEASE_ASSET:
        raise ArchivalError(f"GitHub Release per-asset limit exceeded: {path.name}")
    if digest_file(path) != digest:
        raise ArchivalError(f"SHA256 mismatch: {path.name}")


def stream_digest(parts: list[Path]) -> str:
    sha = hashlib.sha256()
    for path in parts:
        with path.open("rb") as reader:
            for chunk in iter(lambda: reader.read(8 * 1024 * 1024), b""):
                sha.update(chunk)
    return sha.hexdigest()


def validate_local(data_dir: Path, manifest_path: Path) -> dict[str, Path]:
    if data_dir.is_symlink() or not data_dir.is_dir():
        raise ArchivalError("evidence directory missing or symbolic link")
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ArchivalError("frozen source manifest is missing or symbolic link")
    if manifest_path.name != MANIFEST_NAME:
        raise ArchivalError("frozen source manifest filename differs from approved release asset name")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("frozen_source_commit") != SOURCE_COMMIT:
        raise ArchivalError("unrecognized frozen source commit")
    if manifest.get("provenance", {}).get("original_receipt_raw_bytes_available") is not False:
        raise ArchivalError("receipt-state provenance unexpectedly changed")
    if manifest.get("science", {}).get("unseen_generalization_claim_authorized") is not False:
        raise ArchivalError("scientific authorization must remain false")
    entries = manifest.get("files")
    if not isinstance(entries, list) or sorted(x.get("name", "") for x in entries) != sorted(EXPECTED_PARTS):
        raise ArchivalError("exact six source-part names required")
    checked: dict[str, Path] = {}
    for entry in entries:
        name = entry["name"]
        path = data_dir / name
        check_file(path, entry["size_bytes"], entry["sha256"])
        checked[name] = path
    summary = data_dir / SUMMARY_NAME
    if summary.is_symlink() or not summary.is_file():
        raise ArchivalError("original verified summary JSON is missing")
    check_file(summary, summary.stat().st_size, EXPECTED_SUMMARY_DIGEST)
    if manifest.get("validation", {}).get("summary_json_sha256") != EXPECTED_SUMMARY_DIGEST:
        raise ArchivalError("summary manifest digest differs from fixed receipt")
    for label, names in (
        ("membership", EXPECTED_PARTS[:5]),
        ("overlap", EXPECTED_PARTS[5:]),
    ):
        actual = stream_digest([checked[n] for n in names])
        expected = EXPECTED_SOURCE_DIGESTS[label]
        if actual != expected or manifest.get("validation", {}).get(
            f"compressed_{label}_sha256"
        ) != expected:
            raise ArchivalError(f"{label} compressed stream digest mismatch")
    checked[SUMMARY_NAME] = summary
    checked[MANIFEST_NAME] = manifest_path
    print("SALEX_RELEASE_LOCAL_SHA256_PASS parts=6 summary=1 manifest=1")
    return checked


def gh(args: list[str], *, allow_not_found: bool = False) -> dict | None:
    try:
        completed = subprocess.run(
            ["gh", *args], text=True, encoding="utf-8", errors="replace",
            capture_output=True, check=False, timeout=900,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ArchivalError(f"GitHub CLI unavailable: {type(exc).__name__}") from exc
    if completed.returncode:
        # Never print untrusted provider text; it could include credentials.
        if allow_not_found and (
            "HTTP 404" in completed.stderr or
            "HTTP 404" in completed.stdout or
            "Not Found (HTTP 404)" in completed.stderr
        ):
            return None
        raise ArchivalError(f"GitHub operation failed (exit={completed.returncode}); verify gh auth status / repository permissions")
    if args and args[0] == "api":
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ArchivalError("GitHub returned non-JSON response") from exc
    return {}


def github_api(resource: str, *, allow_not_found: bool = False) -> dict | None:
    return gh(["api", resource], allow_not_found=allow_not_found)


def verify_release_metadata(tag: str) -> dict | None:
    # GitHub's /releases/tags/{tag} endpoint may return 404 for a DRAFT,
    # even when the authenticated releases LIST already contains that draft.
    # Do not interpret that 404 as absence: it led to the failed first upload
    # and could cause duplicate creation on retries.
    releases = github_api(f"repos/{REPO}/releases?per_page=100")
    if not isinstance(releases, list):
        raise ArchivalError("authenticated release list is unavailable")
    matched = [item for item in releases if item.get("tag_name") == tag]
    if len(matched) > 1:
        # Earlier code created a duplicate empty draft after a tag-API 404.
        # Never delete a draft; select only the original pinned ID, and only
        # after confirming all other same-tag drafts have no assets.
        if not any(item.get("id") == CANONICAL_DRAFT_RELEASE_ID for item in matched):
            raise ArchivalError("canonical original release ID is absent")
        for item in matched:
            if item.get("id") == CANONICAL_DRAFT_RELEASE_ID:
                continue
            if item.get("draft") is not True or item.get("target_commitish") != SOURCE_COMMIT or item.get("assets"):
                raise ArchivalError("duplicate draft is not safely empty; manual review required")
        matched = [item for item in matched if item.get("id") == CANONICAL_DRAFT_RELEASE_ID]
        print("SALEX_RELEASE_DUPLICATE_EMPTY_DRAFTS: original release selected")
    if matched:
        release_id = matched[0].get("id")
        if release_id != CANONICAL_DRAFT_RELEASE_ID:
            raise ArchivalError("unexpected release ID; manual review required")
        if not isinstance(release_id, int):
            raise ArchivalError("release ID missing")
        release = github_api(f"repos/{REPO}/releases/{release_id}")
        if release is None:
            raise ArchivalError("listed draft release cannot be retrieved by ID")
    else:
        if len(releases) == 100:
            # Do not create another release when a relevant draft might be on
            # an unexamined page. Fail closed until pagination is implemented.
            raise ArchivalError("release list is full; manual draft ID review required")
        return None
    if release.get("tag_name") != TAG or release.get("draft") is not True:
        raise ArchivalError("release is not the expected editable DRAFT")
    if release.get("target_commitish") != SOURCE_COMMIT:
        raise ArchivalError("release target commit is not the frozen Kaggle source commit")
    git_ref = github_api(f"repos/{REPO}/git/ref/tags/{tag}", allow_not_found=True)
    # GitHub draft releases can defer materializing a new tag until publish.
    # When no ref exists, the draft's exact target_commitish still binds it.
    # When a ref DOES exist, it must resolve to the expected frozen commit.
    if git_ref is not None and (
        git_ref.get("object", {}).get("type") != "commit"
        or git_ref["object"].get("sha") != SOURCE_COMMIT
    ):
        raise ArchivalError("existing release tag does not resolve to the frozen source commit")
    return release


def validate_assets(release: dict, files: dict[str, Path]) -> set[str]:
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise ArchivalError("release asset list is unavailable")
    expected = {name: (path.stat().st_size, digest_file(path)) for name, path in files.items()}
    remote_names: set[str] = set()
    for asset in assets:
        name = asset.get("name", "")
        if name in remote_names or name not in expected:
            raise ArchivalError("unexpected or duplicate asset on existing draft")
        remote_names.add(name)
        size, digest = expected[name]
        if asset.get("size") != size or asset.get("digest") != f"sha256:{digest}" or asset.get("state") != "uploaded":
            raise ArchivalError(f"remote asset digest/state mismatch: {name}")
    return remote_names


def prepare_notes(path: Path) -> None:
    path.write_text(
        "# Preserved Phase 3 sAlex scientific evidence (draft; review before publishing)\n\n"
        f"- Original Kaggle source commit: \u0060{SOURCE_COMMIT}\u0060\n"
        "- Original compressed sAlex membership parts: 5\n"
        "- Original compressed WBM–sAlex overlap parts: 1\n"
        "- Summary JSON: byte-exact hash checked locally\n"
        "- Independent frozen part/stream SHA256: checked before upload\n"
        "- Original execution receipt JSON RAW BYTES: NOT AVAILABLE; do not fabricate\n"
        "- GitHub remote asset SHA256 and size: verified before marking upload complete\n"
        "- Earlier local SQLite/JSONL raw validation is historical, not re-executed here\n"
        "- Full training lineage (MPTrj): NOT ATTESTED\n"
        "- Unseen generalization claims: NOT AUTHORIZED\n"
        "- Source-data redistribution license and scientific publication review: REQUIRED\n\n"
        "Do not publish until redistribution rights and provenance limits are reviewed. "
        "Release remains a draft, and no Kaggle compute is submitted.\n",
        encoding="utf-8",
    )


def create_or_resume_draft(files: dict[str, Path]) -> str:
    if not shutil.which("gh"):
        raise ArchivalError("GitHub CLI (gh) not installed; use 'gh auth login' after installing")
    existing = verify_release_metadata(TAG)
    if existing is None:
        # Do not adopt an unrelated tag or upload into a pre-existing wrong ref.
        tag_ref = github_api(f"repos/{REPO}/git/ref/tags/{TAG}", allow_not_found=True)
        if tag_ref is not None:
            raise ArchivalError("tag exists without the expected draft release")
        with tempfile.TemporaryDirectory(prefix="rhombus-release-notes-") as tmp:
            notes = Path(tmp) / "release-notes.md"
            prepare_notes(notes)
            gh([
                "release", "create", TAG, "--repo", REPO, "--draft",
                "--target", SOURCE_COMMIT, "--title", TITLE, "--notes-file", str(notes),
                "--latest=false",
            ])
        existing = verify_release_metadata(TAG)
        if existing is None:
            raise ArchivalError("created draft release cannot be read back")
    uploaded = validate_assets(existing, files)
    for name, path in files.items():
        if name in uploaded:
            print(f"SALEX_RELEASE_ALREADY_VERIFIED {name}")
            continue
        # By-tag uploads are ambiguous when duplicate drafts share a tag.
        # Target the original release ID with the official upload endpoint.
        from urllib.parse import quote
        endpoint = (
            f"repos/{REPO}/releases/{CANONICAL_DRAFT_RELEASE_ID}/assets"
            f"?name={quote(name, safe='')}"
        )
        response = gh([
            "api", "--method", "POST",
            f"https://uploads.github.com/{endpoint}",
            "-H", "Content-Type: application/octet-stream",
            "--input", str(path),
        ])
        if not isinstance(response, dict) or response.get("name") != name:
            raise ArchivalError(f"GitHub upload response missing expected asset: {name}")
        current = None
        for _ in range(5):
            current = verify_release_metadata(TAG)
            if current is not None:
                try:
                    present = validate_assets(current, files)
                except ArchivalError:
                    raise
                if name in present:
                    break
            time.sleep(2)
        else:
            raise ArchivalError(f"uploaded asset not verified by GitHub digest: {name}")
        print(f"SALEX_RELEASE_REMOTE_SHA256_PASS {name}")
    final = verify_release_metadata(TAG)
    if final is None or set(files) != validate_assets(final, files):
        raise ArchivalError("draft release has missing or unverified assets")
    print(f"SALEX_RELEASE_DRAFT_VERIFIED https://github.com/{REPO}/releases")
    print("PUBLICATION_NOT_AUTHORIZED; original receipt raw bytes unavailable")
    return TAG


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=MANIFEST_DEFAULT)
    ap.add_argument("--upload-draft", action="store_true", help="Explicitly create/update DRAFT release after local checks")
    args = ap.parse_args(argv)
    try:
        files = validate_local(args.data_dir, args.manifest)
        if args.upload_draft:
            create_or_resume_draft(files)
        else:
            print("DRY_RUN_ONLY: no GitHub writes. Add --upload-draft to archive.")
        return 0
    except (ArchivalError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"SALEX_RELEASE_FAIL_CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
