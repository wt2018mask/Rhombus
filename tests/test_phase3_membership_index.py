from __future__ import annotations

import json
from pathlib import Path

import pytest

from rhombus.domain import (
    MembershipIndexRecord,
    build_membership_index,
    candidate_locators_for_near_duplicate,
    exact_membership_count,
)


SHA_A = "a" * 64
SHA_B = "b" * 64


def _record(
    index: int,
    *,
    dataset_id: str = "MPTrj",
    record_id: str | None = None,
) -> MembershipIndexRecord:
    return MembershipIndexRecord(
        dataset_id=dataset_id,
        record_id=record_id or f"record-{index}",
        source_locator=f"archive/member-{index}",
        composition_key="Li2O" if index % 2 == 0 else "Li3N",
        site_count=3 if index % 2 == 0 else 4,
        structure_fingerprint_sha256=SHA_A if index in {0, 2} else f"{index:064x}",
        prototype_group="proto:a" if index < 3 else "proto:b",
    )


def test_file_membership_index_builds_from_single_pass_generator(
    tmp_path: Path,
) -> None:
    seen: list[int] = []

    def records():
        for index in range(2500):
            seen.append(index)
            yield _record(index)

    path = tmp_path / "membership-index"
    summary = build_membership_index(
        records(),
        path,
        dataset_id="MPTrj",
        source_file_sha256=SHA_B,
        fingerprint_protocol_id="fingerprint:v1",
        prototype_group_protocol_id="prototype:v1",
        chunk_size=17,
    )

    assert summary.row_count == 2500
    assert seen == list(range(2500))
    assert exact_membership_count(path, SHA_A) == 2

    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["source_file_sha256"] == SHA_B
    assert metadata["row_count"] == 2500
    assert metadata["files"]["record"] == "record.tsv"
    assert set(metadata["bucket_offsets"]) == {
        "record.tsv",
        "exact.tsv",
        "near.tsv",
        "prototype.tsv",
    }


def test_file_membership_index_supports_near_duplicate_prefilter(
    tmp_path: Path,
) -> None:
    path = tmp_path / "membership-index"
    build_membership_index(
        (_record(index) for index in range(8)),
        path,
        dataset_id="MPTrj",
        source_file_sha256=SHA_B,
        fingerprint_protocol_id="fingerprint:v1",
        prototype_group_protocol_id="prototype:v1",
        chunk_size=2,
    )

    assert candidate_locators_for_near_duplicate(
        path,
        composition_key="Li2O",
        site_count=3,
    ) == (
        "archive/member-0",
        "archive/member-2",
        "archive/member-4",
        "archive/member-6",
    )


def test_file_membership_index_fails_closed_without_final_directory(
    tmp_path: Path,
) -> None:
    path = tmp_path / "membership-index"

    def records():
        yield _record(0)
        yield _record(1, dataset_id="sAlex")

    with pytest.raises(ValueError, match="does not match"):
        build_membership_index(
            records(),
            path,
            dataset_id="MPTrj",
            source_file_sha256=SHA_B,
            fingerprint_protocol_id="fingerprint:v1",
            prototype_group_protocol_id="prototype:v1",
            chunk_size=1,
        )

    assert path.exists() is False


def test_file_membership_index_rejects_duplicate_record_ids(
    tmp_path: Path,
) -> None:
    path = tmp_path / "membership-index"

    with pytest.raises(ValueError, match="duplicate record_id"):
        build_membership_index(
            (_record(index, record_id="same-id") for index in range(2)),
            path,
            dataset_id="MPTrj",
            source_file_sha256=SHA_B,
            fingerprint_protocol_id="fingerprint:v1",
            prototype_group_protocol_id="prototype:v1",
            chunk_size=1,
        )

    assert path.exists() is False


def test_file_membership_index_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "membership-index"
    path.mkdir()

    with pytest.raises(FileExistsError):
        build_membership_index(
            (),
            path,
            dataset_id="MPTrj",
            source_file_sha256=SHA_B,
            fingerprint_protocol_id="fingerprint:v1",
            prototype_group_protocol_id="prototype:v1",
        )
