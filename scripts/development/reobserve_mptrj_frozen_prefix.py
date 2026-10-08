"""Optional one-Range-GET re-observation of the frozen REAL MPTrj first frame.

No default remote execution, no raw-source persistence, no whole-file reads.
Matching 256KiB SHA256 is NOT full-source or MACE training attestation.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import hmac
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request

from rhombus.domain.mptrj_artifact_zip import verify_mptrj_diagnostic_zip_binding
from rhombus.domain.mptrj_probe_receipt import validate_mptrj_first_frame_receipt
from scripts.development.probe_mptrj_source_prefix import (
    DEFAULT_PREFIX_BYTES, probe_https_range,
)
from scripts.development.verify_mptrj_probe_receipt import _unique_pairs
from scripts.development.verify_mptrj_source import canonical_source

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = ROOT / "data/development/observations/mptrj-run-37852263493"
EXPECTED_RUN_ID = 37852263493
EXPECTED_SOURCE_SHA_PREFIX = "60bb86a8f7d2c8cc5a4ec86dc49263c7abbb820a41eeee6f0b405746603c2ae2"
EXPECTED_GITHUB_ZIP_SHA = "1704ce3ead958a853364129ff1554b07f8e031409ff7732271e4e979154fd231"
EXPECTED_HEAD_SHA = "573fda0c5e5604911416d2746c2d7e7eb23cbbf8"


class MPTrjReobservationError(ValueError):
    """Frozen evidence invalid or a new limited source observation disagrees."""


def _read_bounded_json(path: Path, limit: int) -> dict:
    if path.is_symlink() or not path.is_file() or not 1 <= path.stat().st_size <= limit:
        raise MPTrjReobservationError("frozen manifest/receipt is not a bounded regular file")
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    if not 1 <= len(raw) <= limit:
        raise MPTrjReobservationError("frozen JSON exceeds bounded read")
    obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    if not isinstance(obj, dict):
        raise MPTrjReobservationError("frozen evidence JSON root is not an object")
    return obj


def read_frozen_first_frame(*, evidence_dir: Path = EVIDENCE_DIR) -> dict:
    """Verify the git-retained actual ZIP + JSON before any optional remote GET."""
    root = _read_bounded_json(evidence_dir / "manifest.json", 24 * 1024)
    run = root.get("github_run")
    artifact = root.get("github_artifact")
    observed = root.get("observation")
    claims = root.get("limits_and_claims")
    if (root.get("schema_version") != "rhombus-phase3-mptrj-observation-preservation-v1"
            or not all(isinstance(v, dict) for v in (run, artifact, observed, claims))):
        raise MPTrjReobservationError("frozen real observation manifest schema invalid")
    if (type(run.get("run_id")) is not int or run["run_id"] != EXPECTED_RUN_ID
            or run.get("head_sha") != EXPECTED_HEAD_SHA
            or run.get("event") != "workflow_dispatch" or run.get("conclusion") != "success"):
        raise MPTrjReobservationError("frozen manual-run evidence identity mismatch")
    if (artifact.get("archive_sha256") != EXPECTED_GITHUB_ZIP_SHA
            or artifact.get("github_api_digest") != "sha256:" + EXPECTED_GITHUB_ZIP_SHA
            or observed.get("prefix_sha256") != EXPECTED_SOURCE_SHA_PREFIX):
        raise MPTrjReobservationError("frozen baseline digest is not the real observed anchor")
    must_remain_false = (
        "original_256k_raw_prefix_preserved", "full_original_source_sha256_verified",
        "mace_mpa0_checkpoint_training_membership_attested",
        "model_training_selection_manifest_attested", "execute_exposure_audit",
        "empirical_calibration_use", "unseen_generalization_claim",
        "github_signed_provenance_attested",
    )
    if any(claims.get(key) is not False for key in must_remain_false):
        raise MPTrjReobservationError("unsupported frozen scientific claim")
    archive_path = evidence_dir / "diagnostic.zip"
    receipt_path = evidence_dir / "mptrj-first-frame-observation.json"
    bound = verify_mptrj_diagnostic_zip_binding(
        archive_path, receipt_path,
        expected_artifact_digest="sha256:" + EXPECTED_GITHUB_ZIP_SHA,
    )
    receipt = _read_bounded_json(receipt_path, 16 * 1024)
    validated = validate_mptrj_first_frame_receipt(
        receipt, expected_prefix_bytes=DEFAULT_PREFIX_BYTES,
    )
    if (validated["report_metadata_sha256"] != artifact.get("canonical_receipt_metadata_sha256")
            or bound["receipt_byte_sha256"] != artifact.get("member_sha256")
            or sha256(receipt_path.read_bytes()).hexdigest() != artifact.get("member_sha256")):
        raise MPTrjReobservationError("frozen canonical receipt fingerprint mismatch")
    prior = receipt["observation"]
    if (prior["prefix_sha256"] != EXPECTED_SOURCE_SHA_PREFIX
            or observed.get("first_material_id") != prior["first_material_id"]
            or observed.get("first_frame_id") != prior["first_frame_id"]
            or observed.get("site_count") != prior["first_frame_structure"]["site_count"]
            or observed.get("reduced_formula") != prior["first_frame_structure"]["reduced_formula"]
            or observed.get("energy_fields_present") != prior["first_frame_structure"]["energy_fields_present"]):
        raise MPTrjReobservationError("frozen first-frame observation disagrees with retained receipt")
    return receipt


def compare_bounded_mptrj_observations(
    new_report: dict, prior_receipt: dict,
) -> dict:
    """Require exact prefix digest and structural results; ignore CDN hostname."""
    validate_mptrj_first_frame_receipt(new_report, expected_prefix_bytes=DEFAULT_PREFIX_BYTES)
    validate_mptrj_first_frame_receipt(prior_receipt, expected_prefix_bytes=DEFAULT_PREFIX_BYTES)
    current = new_report["observation"]
    previous = prior_receipt["observation"]
    if not hmac.compare_digest(current["prefix_sha256"], previous["prefix_sha256"]):
        raise MPTrjReobservationError("new 256KiB source bytes differ from frozen prefix SHA256")
    for key in (
        "prefix_size_bytes", "first_material_id", "first_frame_id",
        "first_frame_structure_object_start_seen", "complete_frame_parsed",
        "first_frame_structure", "complete_original_source_hashed",
    ):
        if current[key] != previous[key]:
            raise MPTrjReobservationError(f"source first-frame disagreement: {key}")
    for key in (
        "figshare_file_id", "expected_total_size_bytes_from_registry",
        "server_content_range_total_declared",
    ):
        if new_report["source_metadata"][key] != prior_receipt["source_metadata"][key]:
            raise MPTrjReobservationError(f"source range identity disagreement: {key}")
    return {
        "schema_version": "rhombus-phase3-mptrj-bounded-prefix-reobservation-v1",
        "status": "SAME_256K_PREFIX_SHA256_AND_FIRST_FRAME_ONLY",
        "frozen_run_id": EXPECTED_RUN_ID,
        "prefix_bytes": DEFAULT_PREFIX_BYTES,
        "prefix_sha256": current["prefix_sha256"],
        "first_material_id": current["first_material_id"],
        "first_frame_id": current["first_frame_id"],
        "site_count": current["first_frame_structure"]["site_count"],
        "redirect_host_may_differ": True,
        "full_original_source_sha256_verified": False,
        "mace_mpa0_training_membership_attested": False,
        "execute_exposure_audit": False,
        "empirical_calibration_use": False,
        "unseen_generalization_claim": False,
    }


def reobserve_frozen_mptrj_prefix(*, open_url=urllib.request.urlopen) -> dict:
    """Opt-in caller only; exactly one bounded HTTP Range GET, no disk writes."""
    prior = read_frozen_first_frame()
    registry = canonical_source()
    if registry["size"] != prior["source_metadata"]["expected_total_size_bytes_from_registry"]:
        raise MPTrjReobservationError("canonical source size changed since frozen first observation")
    new = probe_https_range(
        expected_total=registry["size"],
        prefix_bytes=DEFAULT_PREFIX_BYTES,
        require_complete_frame=True,
        open_url=open_url,
    )
    return compare_bounded_mptrj_observations(new, prior)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reobserve", action="store_true",
        help="explicitly authorize one strictly bounded remote 256KiB Range GET",
    )
    args = parser.parse_args(argv)
    try:
        if not args.reobserve:
            raise MPTrjReobservationError("explicit --reobserve required; no network by default")
        result = reobserve_frozen_mptrj_prefix()
    except (ValueError, OSError, TypeError, UnicodeError, urllib.error.URLError) as exc:
        print(f"MPTRJ_FROZEN_PREFIX_REOBSERVATION_REJECTED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("MPTRJ_REAL_FIRST_FRAME_256K_SOURCE_REOBSERVATION_CONCORDANT")
    print(f"PREFIX_SHA256={result['prefix_sha256']}")
    print(f"MATERIAL_ID={result['first_material_id']}; FRAME_ID={result['first_frame_id']}")
    print("SOURCE_SHA256_NOT_FROZEN; MACE_MPA0_TRAINING_MEMBERSHIP_UNATTESTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
