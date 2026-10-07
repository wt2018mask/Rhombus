from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterator

from rhombus.domain.membership import MembershipIndexRecord, build_membership_index


def iter_normalized_records(path: Path) -> Iterator[MembershipIndexRecord]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            try:
                yield MembershipIndexRecord(
                    dataset_id=payload["dataset_id"],
                    record_id=payload["record_id"],
                    source_locator=payload["source_locator"],
                    composition_key=payload["composition_key"],
                    site_count=int(payload["site_count"]),
                    structure_fingerprint_sha256=payload[
                        "structure_fingerprint_sha256"
                    ],
                    prototype_group=payload["prototype_group"],
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"invalid normalized membership row at line {line_number}"
                ) from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-jsonl", required=True)
    parser.add_argument("--output-sqlite", required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--source-file-sha256", required=True)
    parser.add_argument("--fingerprint-protocol-id", required=True)
    parser.add_argument("--prototype-group-protocol-id", required=True)
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()

    summary = build_membership_index(
        iter_normalized_records(Path(args.input_jsonl)),
        Path(args.output_sqlite),
        dataset_id=args.dataset_id,
        source_file_sha256=args.source_file_sha256,
        fingerprint_protocol_id=args.fingerprint_protocol_id,
        prototype_group_protocol_id=args.prototype_group_protocol_id,
        batch_size=args.batch_size,
    )

    print(
        "MEMBERSHIP_INDEX_BUILT "
        f"dataset_id={summary.dataset_id} "
        f"rows={summary.row_count} "
        f"source_sha256={summary.source_file_sha256} "
        f"path={summary.index_path}"
    )


if __name__ == "__main__":
    main()
