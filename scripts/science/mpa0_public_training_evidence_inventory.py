"""0141 read-only scoped Git-tree/release evidence inventory for MACE-MPA-0.

A path in a published repository cannot certify that it was selected to
train this checkpoint. Only fixed boolean counters leave the process.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

SCHEMA = "rhombus-mpa0-pinned-public-repository-inventory-0141-v1"
FOUNDATIONS_COMMIT = "16a9f178706ce053f3ca8531efbab00a305d0854"
MACE_COMMIT = "0f5de4b15d9c7f86d4e50996533ecf6c0f48a51b"
MODEL_PATH = "mace/calculators/foundations_models/mace-mpa-0-medium.model"
GOLDEN_TEST_MANIFEST_PATH = "tests/golden/fixtures/manifest.json"
GENERIC_FINE_TUNING_SELECTOR_PATH = "mace/cli/fine_tuning_select.py"
RELEASE_TAG = "mace_mpa_0"
RELEASE_ASSET_ID = 213937064
ASSET_NAME = "mace-mpa-0-medium.model"
ASSET_BYTES = 79462305
RELEASE_URL = "https://github.com/ACEsuit/mace-foundations/releases/download/mace_mpa_0/mace-mpa-0-medium.model"
# No generic substring search for a "manifest" may be treated as membership.
MAX_JSON = 1_000_000
MAX_ENTRIES = 2000
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SAFE = re.compile(r"^[A-Za-z0-9_.+/@-]{1,500}$")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate upstream JSON property")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("non-JSON numeric constant in upstream observation")


def read_bounded_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("source must be regular JSON file")
    with path.open("rb") as src:
        raw = src.read(MAX_JSON + 1)
    if not raw or len(raw) > MAX_JSON:
        raise ValueError("bounded external JSON exceeds byte limit")
    data = json.loads(raw, object_pairs_hook=_unique, parse_constant=_reject_constant)
    if not isinstance(data, dict):
        raise ValueError("upstream GitHub payload must be object")
    return data


def _paths_of_exact_tree(tree: dict, commit: str) -> dict:
    if tree.get("sha") != commit or tree.get("truncated") is not False:
        raise ValueError("pinned GitHub Git tree identity or completeness mismatch")
    rows = tree.get("tree")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ENTRIES:
        raise ValueError("invalid Git tree entries")
    paths = {}
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("invalid Git tree node")
        path = item.get("path")
        if (not isinstance(path, str) or not _SAFE.fullmatch(path)
            or path.startswith("/") or path.endswith("/")
            or any(segment in ("", ".", "..") for segment in path.split("/"))
            or path in paths):
            raise ValueError("unsafe or duplicate Git tree path")
        kind = item.get("type")
        mode = item.get("mode")
        if (kind == "tree" and mode != "040000") or (
            kind == "blob" and mode not in ("100644", "100755")
        ) or kind not in ("tree", "blob"):
            raise ValueError("unexpected git item type or mode")
        digest = item.get("sha")
        if not isinstance(digest, str) or not _COMMIT.fullmatch(digest):
            raise ValueError("invalid original Git blob SHA")
        size = item.get("size")
        if kind == "blob" and (type(size) is not int or size < 0 or size > 100000000):
            raise ValueError("invalid Git blob size")
        paths[path] = item
    return paths


def _verified_release(release: dict) -> None:
    if release.get("tag_name") != RELEASE_TAG:
        raise ValueError("official model release tag mismatch")
    assets = release.get("assets")
    if not isinstance(assets, list) or len(assets) > 100:
        raise ValueError("invalid official release asset inventory")
    target = [a for a in assets if isinstance(a, dict) and a.get("id") == RELEASE_ASSET_ID]
    if len(target) != 1:
        raise ValueError("exact MACE-MPA-0 release asset id missing or duplicate")
    asset = target[0]
    if (asset.get("name") != ASSET_NAME or type(asset.get("size")) is not int
        or asset["size"] != ASSET_BYTES or
        asset.get("browser_download_url") != RELEASE_URL):
        raise ValueError("official release asset binding mismatch")


def audit_public_availability(
    *, foundations_tree: dict, mace_tree: dict, release: dict,
) -> dict:
    foundations_paths = _paths_of_exact_tree(foundations_tree, FOUNDATIONS_COMMIT)
    mace_paths = _paths_of_exact_tree(mace_tree, MACE_COMMIT)
    _verified_release(release)
    model = mace_paths.get(MODEL_PATH)
    if not model or model["type"] != "blob" or model["size"] != ASSET_BYTES:
        raise ValueError("pinned MACE source repository model file unavailable")
    if GOLDEN_TEST_MANIFEST_PATH not in mace_paths:
        raise ValueError("expected golden test fixture not found at pinned source")
    if GENERIC_FINE_TUNING_SELECTOR_PATH not in mace_paths:
        raise ValueError("expected reusable finetuning tool not found at pinned source")
    # Deliberately do NOT identify a random file as training membership.
    return {
        "schema_version": SCHEMA,
        "pinned_model_implementation_repo": "ACEsuit/mace",
        "pinned_model_implementation_commit": MACE_COMMIT,
        "model_implementation_git_tree_entries": len(mace_paths),
        "pinned_foundation_repo": "ACEsuit/mace-foundations",
        "pinned_foundation_commit": FOUNDATIONS_COMMIT,
        "foundations_git_tree_entries": len(foundations_paths),
        "all_two_pinned_public_tree_listings_complete": True,
        "official_release_asset_id": RELEASE_ASSET_ID,
        "official_release_asset_bytes_declared": ASSET_BYTES,
        "pinned_repository_contains_model_binary_path": True,
        "test_golden_manifest_present_NOT_training_frame_manifest": True,
        "generic_fine_tuning_selector_present_NOT_actual_selection": True,
        "source_tree_audit_scope_EXCLUDES_other_repositories_releases_external_storage": True,
        "actual_selected_MPTrj_frame_ids_authenticated": False,
        "actual_selected_sAlex_frame_ids_authenticated": False,
        "training_data_source_SHA256_and_preprocessing_authenticated": False,
        "publisher_signed_checkpoint_specific_training_manifest_available": False,
        "independent_training_manifest_auditor_available": False,
        "checkpoint_binary_byte_rehash_completed_in_0140": True,
        "all_P0_scientific_requirements_satisfied": False,
        "selected_training_membership_verdict": "UNKNOWN",
        "P0_02_status": "BLOCKED",
        "P0_01_status": "BLOCKED",
        "P0_03_status": "BLOCKED",
        "scientific_release_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--foundation-tree-json", type=Path, required=True)
    parser.add_argument("--mace-tree-json", type=Path, required=True)
    parser.add_argument("--release-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        sources = [args.foundation_tree_json.resolve(strict=True),
                   args.mace_tree_json.resolve(strict=True),
                   args.release_json.resolve(strict=True)]
        destination = args.output_dir.resolve()
        if len(set(sources)) != 3 or destination.exists() or any(
            destination == s or s in destination.parents for s in sources
        ):
            raise ValueError("input and output files/locations must be disjoint")
        report = audit_public_availability(
            foundations_tree=read_bounded_json(sources[0]),
            mace_tree=read_bounded_json(sources[1]),
            release=read_bounded_json(sources[2]),
        )
        destination.mkdir(parents=True, exist_ok=False)
        (destination / "public_training_evidence_availability.json").write_text(
            json.dumps(report, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
