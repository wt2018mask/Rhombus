"""0140: hash the *full* pinned MACE-MPA-0 public release checkpoint on a CI CPU.

The 79MB binary stays temporary; only a small fixed-schema SHA256 receipt
leaves the runner. A full-file public release checksum DOES NOT prove which
individual MPTrj / sAlex frames were selected during model training.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat

from rhombus.domain.mpa0_publisher_digest import PUBLIC_SHA256, MODEL, RELEASE_URL

SCHEMA = "rhombus-mace-mpa0-release-binary-observation-0140-v1"
ASSET_ID = 213937064
ASSET_SIZE = 79_462_305
SOURCE_REPO = "ACEsuit/mace-foundations"
SOURCE_TAG = "mace_mpa_0"
DOWNLOAD_URL = (
    "https://github.com/ACEsuit/mace-foundations/releases/download/"
    "mace_mpa_0/mace-mpa-0-medium.model"
)
MAX_OBSERVABLE_BYTES = 80_000_000
CHUNK_BYTES = 1 << 20


def _hash_file_full(path: Path, *, expected_size: int, expected_sha256: str) -> tuple[int, str]:
    """Stream and bound a byte-exact file, not a sampled prefix / declared digest."""
    if (
        type(expected_size) is not int or expected_size < 1
        or expected_size > MAX_OBSERVABLE_BYTES
        or not isinstance(expected_sha256, str)
        or len(expected_sha256) != 64
        or any(c not in "0123456789abcdef" for c in expected_sha256)
    ):
        raise ValueError("invalid full-file expected digest or byte budget")
    if path.is_symlink():
        raise ValueError("release model path must not be a symlink")
    file_stat = path.stat()
    if not stat.S_ISREG(file_stat.st_mode):
        raise ValueError("model checkpoint must be a regular file")
    if file_stat.st_size != expected_size:
        raise ValueError("release model checkpoint file size mismatch")
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while True:
            chunk = source.read(CHUNK_BYTES)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_OBSERVABLE_BYTES or size > expected_size:
                raise ValueError("model checkpoint exceeded fixed byte budget")
            h.update(chunk)
    if size != expected_size:
        raise ValueError("incomplete model checkpoint read")
    observed = h.hexdigest()
    if observed != expected_sha256:
        raise ValueError("model release full-file SHA256 does not match pinned publisher digest")
    return size, observed


def observe_mpa0_official_release_file(path: Path) -> dict:
    """Only official hard-pinned asset identity is ever accepted by this API."""
    if not isinstance(path, Path):
        raise TypeError("binary path must be Path")
    size, sha256 = _hash_file_full(
        path, expected_size=ASSET_SIZE, expected_sha256=PUBLIC_SHA256,
    )
    return {
        "schema_version": SCHEMA,
        "source_repository": SOURCE_REPO,
        "source_release_tag": SOURCE_TAG,
        "source_release_url": RELEASE_URL,
        "source_download_url": DOWNLOAD_URL,
        "source_release_asset_id": ASSET_ID,
        "source_release_asset_name": MODEL,
        "observed_full_file_byte_count": size,
        "observed_full_file_sha256": sha256,
        "publisher_reported_sha256_matched": True,
        "original_model_binary_uploaded_or_republished": False,
        "execution_scope": "GITHUB_ACTIONS_RUNNER_REHASH_NOT_EXTERNAL_AUDITOR",
        "authenticated_independent_scientific_auditor": False,
        "complete_MPtrj_training_source_attested": False,
        "complete_sAlex_training_source_attested": False,
        "checkpoint_selected_MPTrj_frames_attested": False,
        "checkpoint_selected_sAlex_frames_attested": False,
        "training_preprocessing_or_energy_labels_attested": False,
        "model_training_exposure_audit_authorized": False,
        "scientific_blind_qualification_authorized": False,
        "independent_material_statistics_qualified": False,
        "scientific_release_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        original = args.model_binary.absolute()
        out = args.output_dir.absolute()
        if out.exists() or original == out or original in out.parents:
            raise ValueError("receipt destination must be new and separate from binary")
        report = observe_mpa0_official_release_file(original)
        out.mkdir(parents=True, exist_ok=False)
        (out / "mpa0_binary_observation.json").write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n",
            encoding="utf-8",
        )
    except (ValueError, TypeError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
