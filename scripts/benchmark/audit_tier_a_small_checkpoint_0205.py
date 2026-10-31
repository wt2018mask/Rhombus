"""Opt-in full-byte MACE-MP0 small release checksum; no weights retained or loaded.

Expected checksum is an independent third-party report, not a publisher signature.
This is NOT evidence of training lineage, NEB accuracy, or benchmark readiness.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from urllib.request import Request, build_opener

from scripts.science.mace_checkpoint_binary_0175 import (
    AllowPinnedGithubRedirect, hash_full_stream, no_duplicate_fields,
    require_source_url, MAX_METADATA_BYTES,
)

TAG = "mace_mp_0"
NAME = "2023-12-10-mace-128-L0_energy_epoch-249.model"
URL = "https://github.com/ACEsuit/mace-foundations/releases/download/" + TAG + "/" + NAME
RELEASE = "https://api.github.com/repos/ACEsuit/mace-foundations/releases/tags/" + TAG
SIZE = 32581838
ASSET_ID = 145021750
THIRD_PARTY_SHA256 = "2ddb079cee0e131eaaf6912ba581b394551ead283e95c99cfe78c605d10b5736"


def verify_release(meta):
    if (type(meta) is not dict or meta.get("tag_name") != TAG
            or meta.get("draft") is not False or meta.get("prerelease") is not False):
        raise ValueError("OFFICIAL_SMALL_RELEASE_IDENTITY_MISMATCH")
    assets = meta.get("assets")
    if type(assets) is not list or not 1 <= len(assets) <= 50:
        raise ValueError("AMBIGUOUS_RELEASE_ASSETS")
    matches = [a for a in assets if type(a) is dict and a.get("name") == NAME]
    if len(matches) != 1:
        raise ValueError("NONUNIQUE_SMALL_MODEL_ASSET")
    a = matches[0]
    if (type(a.get("id")) is not int or a["id"] != ASSET_ID
            or type(a.get("size")) is not int or a["size"] != SIZE
            or a.get("state") != "uploaded"
            or a.get("browser_download_url") != URL
            or a.get("digest") not in (None, "sha256:" + THIRD_PARTY_SHA256)):
        raise ValueError("SMALL_MODEL_ASSET_IDENTITY_DRIFT")
    return {"asset_id": ASSET_ID, "asset_bytes": SIZE,
            "official_api_sha256": a.get("digest"),
            "expected_sha256_origin": "THIRD_PARTY_ENCCS_AND_HF_NOT_PUBLISHER_SIGNED"}


def observe_release_bytes():
    opener = build_opener(AllowPinnedGithubRedirect())
    with opener.open(Request(RELEASE, headers={
        "User-Agent": "Rhombus-0205-small-checkpoint-audit",
        "Accept": "application/vnd.github+json"}), timeout=40) as r:
        require_source_url(r.geturl(), frozenset(("api.github.com",)))
        if r.status != 200:
            raise ValueError("NO_OFFICIAL_RELEASE_METADATA")
        raw = r.read(MAX_METADATA_BYTES + 1)
    if not raw or len(raw) > MAX_METADATA_BYTES:
        raise ValueError("RELEASE_METADATA_BUDGET_EXCEEDED")
    meta = json.loads(raw, object_pairs_hook=no_duplicate_fields,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    identity = verify_release(meta)
    with opener.open(Request(URL, headers={
        "User-Agent": "Rhombus-0205-full-byte-read-no-model-execution",
        "Accept": "application/octet-stream"}), timeout=90) as r:
        observation = hash_full_stream(r, size=SIZE, expected_digest=THIRD_PARTY_SHA256)
    return {
        "schema_version": "rhombus-0205-tier-a-small-model-full-byte-identity-v1",
        "source_identity": identity, "full_byte_observation": observation,
        "publisher_signature_verified": False, "training_lineage_verified": False,
        "model_loaded": False, "model_executed": False,
        "execution_authorized": False, "benchmark_status": "BENCHMARK_NOT_FROZEN",
        "scientific_status": "SCIENTIFIC_NO_GO_ABSTAIN"}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--real-full-byte-audit", action="store_true")
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args(argv)
    if not args.real_full_byte_audit:
        p.error("explicit checkpoint byte-read authorization flag required")
    dest = args.output_dir.resolve()
    if dest.exists() or dest.is_symlink():
        p.error("refuse output overwrite")
    receipt = observe_release_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".rhombus-0205-small-", dir=dest.parent))
    try:
        (temp / "small_model_checksum_0205.json").write_text(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8")
        if dest.exists():
            raise ValueError("OUTPUT_PATH_COLLISION")
        temp.rename(dest)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    print("SMALL_CHECKPOINT_FULL_BYTE_HASH_MATCHES_THIRD_PARTY_NO_SCIENCE_GO")
    return receipt


if __name__ == "__main__":
    main()
