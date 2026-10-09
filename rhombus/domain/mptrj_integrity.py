"""Full-consumption MPTrj frame/byte-identity gate, fixture-tested only.

A successful result establishes original SOURCE integrity and parser coverage,
not MACE-MPA-0 training exposure, model lineage or unseen generalization.
No network access or production index writer is provided.
"""
from __future__ import annotations

import hashlib
from typing import BinaryIO, Callable

from .mptrj import MPTrjFrame, MPTrjFormatError, iter_mptrj_frames


class MPTrjIntegrityError(ValueError):
    """Source stream failed to satisfy frozen whole-file/coverage contract."""


class _BoundedHashingSource:
    def __init__(self, source: BinaryIO, expected_size: int):
        self._source = source
        self._expected_size = expected_size
        self._md5 = hashlib.md5()  # noqa: S324: compare against upstream MD5
        self._sha256 = hashlib.sha256()
        self.size = 0

    def read(self, size: int = -1) -> bytes:
        # ijson's read(0) probe is permitted, but read(-1) is prohibited.
        if size < 0:
            raise MPTrjIntegrityError("unbounded source read not permitted")
        chunk = self._source.read(size)
        if not isinstance(chunk, bytes):
            raise MPTrjIntegrityError("MPTrj source must provide binary bytes")
        self.size += len(chunk)
        if self.size > self._expected_size:
            raise MPTrjIntegrityError("source exceeded expected frozen byte size")
        self._md5.update(chunk)
        self._sha256.update(chunk)
        return chunk

    def finish(self) -> tuple[int, str, str]:
        # The parser is required to consume the only JSON value through EOF.
        # Drain any unread whitespace that was not prefetched by ijson.
        while self.read(64 * 1024):
            pass
        return self.size, self._md5.hexdigest(), self._sha256.hexdigest()


def verify_complete_mptrj_source(
    source: BinaryIO,
    *,
    expected_size: int,
    expected_md5: str,
    expected_frames: int,
    expected_sha256: str | None = None,
    max_frame_events: int = 500_000,
    max_frame_scalar_chars: int = 8 * 1024 * 1024,
    on_progress: Callable[[int, int], None] | None = None,
    on_frame: Callable[[MPTrjFrame], None] | None = None,
    progress_every_frames: int = 5_000,
) -> dict:
    """Consume all MPTrj frames; fail on byte drift, gaps, or parser errors.

    Return a report ONLY after full parsing, matching expected frame count,
    frozen total size, and upstream MD5. SHA256 computed here is local evidence;
    it is not independently attested unless expected_sha256 was supplied.

    Optional callbacks convey NON-AUTHORITATIVE progress, not verified evidence.
    Bytes read reflect parser prefetch, not an exact location of the last frame.
    Callback errors propagate and abort verification.
    """
    if type(progress_every_frames) is not int or progress_every_frames <= 0:
        raise ValueError("progress_every_frames must be a positive integer")
    if on_progress is not None and not callable(on_progress):
        raise ValueError("on_progress must be callable")
    if on_frame is not None and not callable(on_frame):
        raise ValueError("on_frame must be callable")
    if expected_size <= 0 or expected_frames <= 0:
        raise ValueError("expected source size and frame count must be positive")
    if len(expected_md5) != 32:
        raise ValueError("expected_md5 must be a 32-character hex digest")
    try:
        int(expected_md5, 16)
    except ValueError as exc:
        raise ValueError("expected_md5 must be hexadecimal") from exc
    if expected_sha256 is not None:
        if len(expected_sha256) != 64:
            raise ValueError("expected_sha256 must be a 64-character hex digest")
        try:
            int(expected_sha256, 16)
        except ValueError as exc:
            raise ValueError("expected_sha256 must be hexadecimal") from exc

    hashing = _BoundedHashingSource(source, expected_size)
    frames = 0
    for frame in iter_mptrj_frames(
        hashing,
        max_frame_events=max_frame_events,
        max_frame_scalar_chars=max_frame_scalar_chars,
    ):
        frames += 1
        if frames > expected_frames:
            raise MPTrjIntegrityError("frame count exceeded frozen declared count")
        if on_frame is not None:
            on_frame(frame)
        if on_progress is not None and frames % progress_every_frames == 0:
            on_progress(frames, hashing.size)

    size, md5, sha256 = hashing.finish()
    if size != expected_size:
        raise MPTrjIntegrityError(
            f"source size mismatch: expected={expected_size}, observed={size}"
        )
    if md5.lower() != expected_md5.lower():
        raise MPTrjIntegrityError("whole-file Figshare MD5 mismatch")
    if frames != expected_frames:
        raise MPTrjIntegrityError(
            f"frame count mismatch: expected={expected_frames}, observed={frames}"
        )
    if expected_sha256 is not None and sha256.lower() != expected_sha256.lower():
        raise MPTrjIntegrityError("independent SHA256 mismatch")

    return {
        "schema_version": "rhombus-phase3-mptrj-full-frame-source-identity-v1",
        "dataset_id": "MPTrj",
        "source_identity": {
            "byte_count": size,
            "figshare_md5_matched": True,
            "computed_md5": md5,
            "computed_sha256": sha256,
            "independent_sha256_matched": expected_sha256 is not None,
        },
        "frame_coverage": {
            "parsed_frames": frames,
            "complete_json_consumed": True,
            "declared_frame_count_matched": True,
            "streaming_adapter": "ijson-nested-pymatgen-frame-v1",
        },
        "model_training_lineage": {
            "exact_mace_mpa0_training_frame_selection": "UNATTESTED",
            "original_figshare_source_equals_model_training_bytes": False,
        },
        "authorization": {
            "build_source_local_diagnostic_membership": False,
            "execute_wbm_training_exposure_audit": False,
            "empirical_calibration_use": False,
            "unseen_generalization_claim": False,
        },
    }
