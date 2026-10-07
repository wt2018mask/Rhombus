from __future__ import annotations

import json
import sqlite3
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


def _record(index: int, *, dataset_id: str = "MPTrj") -> MembershipIndexRecord:
    return MembershipIndexRecord(
        dataset_id=dataset_id,
        record_id=f"record-{index}",
        source_locator=f"archive/member-{index}",
        composition_key="Li2O" if index % 2 == 0 else "Li3N",
        site_count=3 if index % 2 == 0 else 4,
        structure_fingerprint_sha256=SHA_A if index in {0, 2} else f"{index:064x}",
        prototype_group="proto:a" if index < 3 else "proto:b",
    )


def test_membership_index_builds_from_single_pass_generator(tmp_path: Path) -> None:
    seen: list[int] = []

    def records():
        for index in range(2500):
            seen.append(index)
            yield _record(index)

    path = tmp_path / "membership.sqlite"
    summary = build_membership_index(
        records(),
        path,
        dataset_id="MPTrj",
        source_file_sha256=SHA_B,
        fingerprint_protocol_id="fingerprint:v1",
        prototype_group_protocol_id="prototype:v1",
        batch_size=17,
    )

    assert summary.row_count == 2500
    assert seen == list(range(2500))
    assert exact_membership_count(path, SHA_A) == 2

    with sqlite3.connect(path) as connection:
        row_count = connection.execute("SELECT COUNT(*) FROM membership").fetchone()[0]
        metadata = dict(connection.execute("SELECT key, value FROM metadata").fetchall())

    assert row_count == 2500
    assert metadata["source_file_sha256"] == SHA_B
    assert metadata["row_count"] == "2500"


def test_membership_index_supports_near_duplicate_candidate_prefilter(
    tmp_path: Path,
) -> None:
    path = tmp_path / "membership.sqlite"
    build_membership_index(
        (_record(index) for index in range(8)),
        path,
        dataset_id="MPTrj",
        source_file_sha256=SHA_B,
        fingerprint_protocol_id="fingerprint:v1",
        prototype_group_protocol_id="prototype:v1",
        batch_size=2,
    )

    locators = candidate_locators_for_near_duplicate(
        path,
        composition_key="Li2O",
        site_count=3,
    )

    assert locators == (
        "archive/member-0",
        "archive/member-2",
        "archive/member-4",
        "archive/member-6",
    )


def test_membership_index_fails_closed_and_removes_partial_db(
    tmp_path: Path,
) -> None:
    path = tmp_path / "membership.sqlite"

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
            batch_size=1,
        )

    assert path.exists() is False


def test_membership_index_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "membership.sqlite"
    path.write_bytes(b"existing")

    with pytest.raises(FileExistsError):
        build_membership_index(
            (),
            path,
            dataset_id="MPTrj",
            source_file_sha256=SHA_B,
            fingerprint_protocol_id="fingerprint:v1",
            prototype_group_protocol_id="prototype:v1",
        )


ROOT = Path(__file__).resolve().parents[1]


def test_membership_index_plan_keeps_production_audit_closed() -> None:
    plan = json.loads(
        (ROOT / "data/development/phase3_membership_index_plan_v1.json")
        .read_text(encoding="utf-8")
    )

    assert plan["status"] == "BUILDER_IMPLEMENTED_SOURCE_ADAPTERS_PENDING"
    assert plan["storage"]["write_mode"] == "incremental-batched-commits"
    assert plan["authorization"]["production_membership_index_complete"] is False
    assert plan["authorization"]["execute_exposure_audit"] is False
    assert plan["authorization"]["unseen_generalization_claim"] is False


def test_salex_metadata_identity_does_not_fake_byte_identity() -> None:
    identity = json.loads(
        (ROOT / "data/development/phase3_salex_archive_identity_v1.json")
        .read_text(encoding="utf-8")
    )

    assert identity["declared_content"]["n_structures"] == 10447765
    assert identity["source"]["metadata_repository"] == "facebookresearch/fairchem"
    assert identity["source"]["metadata_commit"] == "3801dac0cc0458a2f8121259a2ce8b23d4dcc5a1"
    assert identity["source"]["metadata_path"] == "docs/inorganic_materials/datasets/omat24.md"
    assert identity["declared_content"]["archive_file_size"] == "7.6 GB (source-declared display size)"
    assert identity["byte_identity"]["status"] == "NOT_FROZEN"
    assert identity["byte_identity"]["sha256"] is None
    assert identity["scientific_policy"][
        "source_declared_filter_equals_complete_membership_audit"
    ] is False
    assert identity["authorization"]["build_membership_index"] is False
    assert identity["authorization"]["execute_exposure_audit"] is False
