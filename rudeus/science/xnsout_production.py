"""Production X -> N -> S -> OUT orchestration.

Consumes replay-verifiable X/N records plus a primary ClaimAssessment, rebuilds
all downstream assessments, and persists S/OUT sidecars atomically. No upstream
scientific verdict is recomputed or upgraded here.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from rudeus.science.contracts import ClaimAssessment, canonical_bytes, digest
from rudeus.science.negative_controls import NAssessment, verify_n_record
from rudeus.science.output import out_record, verify_out_record
from rudeus.science.synthesis import SynthesisAssessment, s_record, verify_s_record
from rudeus.science.xcheck import XAssessment, verify_x_record


class XNSOUTProductionError(RuntimeError):
    pass


def _verified_x_assessments(records: Sequence[Mapping[str, Any]]) -> tuple[XAssessment, ...]:
    out = []
    for record in records:
        verified = verify_x_record(record)
        if verified.get("primary_verdict_changed") is not False:
            raise XNSOUTProductionError("verified X record attempted primary verdict change")
        out.append(XAssessment.from_dict(verified["assessment"]))
    return tuple(out)


def _verified_n_assessments(
    records: Sequence[Mapping[str, Any]],
    *,
    primary: ClaimAssessment,
) -> tuple[NAssessment, ...]:
    out = []
    for record in records:
        verified = verify_n_record(record)
        if verified.get("target_verdict_changed") is not False:
            raise XNSOUTProductionError("verified N record attempted target verdict change")
        assessment = NAssessment.from_dict(record["assessment"])
        if assessment.target_claim_hash != primary.claim_hash:
            raise XNSOUTProductionError("N record targets a different primary claim")
        out.append(assessment)
    return tuple(out)


def build_xnsout_records(
    *,
    primary: ClaimAssessment,
    x_records: Sequence[Mapping[str, Any]] = (),
    n_records: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Replay-verify X/N and build deterministic S/OUT records."""
    xs = _verified_x_assessments(x_records)
    ns = _verified_n_assessments(n_records, primary=primary)

    s = s_record(primary, x_assessments=xs, n_assessments=ns)
    s_verified = verify_s_record(s)
    synthesis = SynthesisAssessment.from_dict(s_verified["record"]["assessment"])

    out = out_record(synthesis)
    out_verified = verify_out_record(out)

    return {
        "stage": "XNSOUT",
        "primary_claim_hash": primary.claim_hash,
        "primary_assessment_hash": primary.content_hash,
        "x_record_hashes": [digest(v) for v in x_records],
        "n_record_hashes": [digest(v) for v in n_records],
        "s_record": s,
        "s_record_hash": s_verified["record_hash"],
        "out_record": out,
        "out_record_hash": out_verified["record_hash"],
        "final_disposition": out_verified["disposition"],
        "final_claim_verdict": out_verified["claim_verdict"],
    }


def _write_append_only(path: Path, value: Mapping[str, Any]) -> None:
    data = canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        if path.read_bytes() != data:
            raise XNSOUTProductionError(
                f"refusing to overwrite different downstream artifact: {path}"
            )
        return

    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(tmp, path)
        except FileExistsError:
            if path.read_bytes() != data:
                raise XNSOUTProductionError(
                    f"downstream artifact appeared with different content: {path}"
                )
    finally:
        tmp.unlink(missing_ok=True)


def persist_xnsout_records(
    *,
    bundle: Mapping[str, Any],
    s_path: str | Path,
    out_path: str | Path,
) -> dict[str, str]:
    """Persist already-built S and OUT records atomically and idempotently."""
    if bundle.get("stage") != "XNSOUT":
        raise XNSOUTProductionError("invalid XNSOUT bundle")
    s = bundle.get("s_record")
    out = bundle.get("out_record")
    if not isinstance(s, Mapping) or not isinstance(out, Mapping):
        raise XNSOUTProductionError("bundle missing S/OUT records")

    verify_s_record(s)
    verify_out_record(out)

    s_path = Path(s_path)
    out_path = Path(out_path)
    _write_append_only(s_path, s)
    _write_append_only(out_path, out)

    return {
        "s_path": str(s_path),
        "s_sha256": digest(s),
        "out_path": str(out_path),
        "out_sha256": digest(out),
    }
