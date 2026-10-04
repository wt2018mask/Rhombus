
import json
from pathlib import Path

from rudeus.mlip.p2 import run_p2_batches


def _write_p1(path: Path, batch_id: str) -> None:
    path.write_text(
        json.dumps(
            {
                "batch_id": batch_id,
                "child_material_id": f"test-material-{batch_id}",
                "parent_id": "test-parent",
                "p0_state": "PLAUSIBLE",
                "result": {
                    "p1_verdict": "KEEP_FOR_P2",
                    "relaxed_structure_dict": {
                        "@module": "pymatgen.core.structure",
                        "@class": "Structure",
                        "charge": 0,
                        "lattice": {
                            "matrix": [
                                [5.0, 0.0, 0.0],
                                [0.0, 5.0, 0.0],
                                [0.0, 0.0, 5.0],
                            ],
                            "pbc": [True, True, True],
                        },
                        "sites": [
                            {
                                "species": [{"element": "Li", "occu": 1.0}],
                                "abc": [0.0, 0.0, 0.0],
                            }
                        ],
                    },
                    "relaxed_structure_sha256": "a" * 64,
                },
            }
        )
    )


def test_target_batch_id_processes_exactly_one_candidate(tmp_path):
    p1 = tmp_path / "p1"
    p2 = tmp_path / "p2"
    p1.mkdir()
    p2.mkdir()

    ids = [
        "01d9c9dd3fe51f40",
        "037d19ae822a0c71",
        "06c995df17893ed0",
    ]

    for batch_id in ids:
        _write_p1(p1 / f"{batch_id}.json", batch_id)

    calls = []

    def fake_runner(job):
        calls.append(job["batch_id"])
        return {
            "status": "DONE",
            "verdict": "FAIL",
            "dynamic_state": "FAIL",
            "termination": {"reason": "explosive-step"},
        }

    summary = run_p2_batches(
        p1,
        p2,
        shard_index=0,
        n_shards=1,
        md_runner=fake_runner,
        protocol={"protocol_version": "test"},
        worker_info={"session": "test", "device": "cpu"},
        allowlist=set(ids),
        target_batch_id="037d19ae822a0c71",
    )

    assert calls == ["037d19ae822a0c71"]
    assert summary["wrote"] == ["037d19ae822a0c71"]
    assert summary["processed"] == 1

    assert not (p2 / "01d9c9dd3fe51f40.json").exists()
    assert (p2 / "037d19ae822a0c71.json").exists()
    assert not (p2 / "06c995df17893ed0.json").exists()


def test_target_batch_id_does_not_change_shard_filter(tmp_path):
    p1 = tmp_path / "p1"
    p2 = tmp_path / "p2"
    p1.mkdir()
    p2.mkdir()

    # This batch is deterministically assigned to shard 0/2:
    # int("06c995df17893ed0", 16) % 2 == 0.
    target = "06c995df17893ed0"
    _write_p1(p1 / f"{target}.json", target)

    calls = []

    def fake_runner(job):
        calls.append(job["batch_id"])
        return {"status": "DONE"}

    # Deliberately use a shard that does not own this batch.
    summary = run_p2_batches(
        p1,
        p2,
        shard_index=1,
        n_shards=2,
        md_runner=fake_runner,
        protocol={"protocol_version": "test"},
        worker_info={"session": "test", "device": "cpu"},
        allowlist={target},
        target_batch_id=target,
    )

    assert calls == []
    assert summary["wrote"] == []
    assert not (p2 / f"{target}.json").exists()
