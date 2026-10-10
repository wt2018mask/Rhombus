"""Artificial identifiers and signing keys only; never real steward evidence."""

import hashlib
import sqlite3

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from rhombus.evidence.receipts import (
    TrustedIssuer,
    canonical_bytes,
    evidence_sha256,
    ZERO_SHA256,
)
from rhombus.qualification.sealed_evaluation import (
    OUTCOMES,
    SCHEMA,
)
from rhombus.domain.mpa0_publisher_digest import (
    PUBLIC_SHA256,
    MODEL,
    RELEASE_URL,
    MACE_REPO_COMMIT,
)
from rhombus.domain.shard_contract import plan_record_shards

ROLES = {
    "steward": "steward",
    "witness": "witness",
    "source": "source_observer",
    "receiver": "storage_receiver",
    "publisher": "publisher",
    "auditor": "lineage_auditor",
    "checkpoint": "checkpoint_observer",
}
KEYS = {
    name: Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(("TEST_ONLY_" + name).encode()).digest()
    )
    for name in ROLES
}


def trust(scope="SYNTHETIC"):
    return {
        name: TrustedIssuer(
            key.public_key().public_bytes_raw(),
            frozenset([ROLES[name]]),
            "synthetic-independent-" + name,
            scope,
            "synthetic-witness-log",
        )
        for name, key in KEYS.items()
    }


def receipt(
    issuer,
    event,
    subject,
    context,
    *,
    scope="SYNTHETIC",
    sequence=1,
    previous=ZERO_SHA256,
):
    body = {
        "schema_version": "rhombus-independent-receipt-v1",
        "issuer": issuer,
        "role": ROLES[issuer],
        "event": event,
        "subject_sha256": subject,
        "context_sha256": context,
        "scope": scope,
        "log_id": "synthetic-witness-log",
        "sequence": sequence,
        "previous_receipt_sha256": previous,
    }
    return {**body, "signature": KEYS[issuer].sign(canonical_bytes(body)).hex()}


def sealed_fixture(outcomes=None, *, scope="SYNTHETIC", repeated=1):
    outcomes = outcomes or list(OUTCOMES)
    tokens = [f"synthetic-material-{n:03}" for n in range(len(outcomes))]
    protocol = {
        "schema_version": SCHEMA,
        "evaluation_id": "synthetic-evaluation",
        "evaluation_version": "synthetic-v1",
        "model_sha256": "a" * 64,
        "cohort_commitment_sha256": evidence_sha256(
            {"material_tokens": sorted(tokens), "nonce": "9" * 64}
        ),
        "scope": scope,
        "development_group": "development",
        "statistical_plan": {
            "sampling_design": "IID_MATERIALS",
            "unit": "MATERIAL",
            "minimum_materials": 100,
            "confidence_level": 0.95,
            "maximum_half_width": 0.1,
            "precision_justification": "Synthetic worst-case Wilson interval design; no empirical power claim.",
            "aggregation": "CONSERVATIVE_UNANIMITY",
            "metric": "CORRECT_FRACTION_ALL_MATERIALS",
            "outcomes": list(OUTCOMES),
        },
    }
    context = evidence_sha256(protocol)
    predictions = {
        "protocol_sha256": context,
        "evaluation_version": protocol["evaluation_version"],
        "model_sha256": protocol["model_sha256"],
        "materials": [
            {
                "material_token": token,
                "trajectories": [outcome] * repeated,
                "material_outcome": outcome,
            }
            for token, outcome in zip(tokens, outcomes)
        ],
    }
    truth = {
        "cohort_nonce": "9" * 64,
        "protocol_sha256": context,
        "evaluation_version": protocol["evaluation_version"],
        "materials": [
            {"material_token": token, "truth_outcome": "POSITIVE"} for token in tokens
        ],
    }
    result = {
        "protocol": protocol,
        "predictions": predictions,
        "truth": truth,
        "trusted_issuers": trust(scope),
    }
    reseal(result)
    return result


def reseal(value):
    p, pred, truth = value["protocol"], value["predictions"], value["truth"]
    context = evidence_sha256(p)
    pred["protocol_sha256"] = truth["protocol_sha256"] = context
    receipts = []
    for n, (issuer, event, subject) in enumerate(
        [
            ("steward", "preregistered", context),
            ("witness", "predictions_committed", evidence_sha256(pred)),
            ("steward", "truth_released", evidence_sha256(truth)),
        ],
        1,
    ):
        receipts.append(
            receipt(
                issuer,
                event,
                subject,
                context,
                scope=p["scope"],
                sequence=n,
                previous=evidence_sha256(receipts[-1]) if receipts else ZERO_SHA256,
            )
        )
    value["receipts"] = receipts


def lineage_fixture(scope="SYNTHETIC"):
    artifacts = {}
    sources = []
    for n, dataset in enumerate(("MPTrj", "sAlex")):
        source_sha = hashlib.sha256(
            ("SYNTHETIC_FULL_SOURCE_" + dataset).encode()
        ).hexdigest()
        common = {
            "checkpoint_sha256": PUBLIC_SHA256,
            "source_sha256": source_sha,
            "dataset_id": dataset,
        }
        frames = {
            "schema_version": "rhombus-checkpoint-frames-v1",
            **common,
            "selection_complete": True,
            "frames": [
                {
                    "frame_id": f"synthetic-frame-{n}",
                    "source_record_id": f"synthetic-record-{n}",
                    "material_token": f"synthetic-training-material-{n}",
                }
            ],
        }
        pre = {
            "schema_version": "rhombus-checkpoint-preprocessing-v1",
            **common,
            "rule": "SYNTHETIC_IDENTITY_NOT_REAL_MACE_PREPROCESSING",
            "publisher_evidence_revision": "synthetic-revision",
        }
        labels = {
            "schema_version": "rhombus-checkpoint-energy_labels-v1",
            **common,
            "labels": [
                {
                    "frame_id": f"synthetic-frame-{n}",
                    "energy_field": "synthetic_energy",
                    "unit": "eV",
                }
            ],
            "publisher_evidence_revision": "synthetic-revision",
        }
        source = {
            "dataset_id": dataset,
            "source_observation": {
                "sha256": source_sha,
                "byte_length": 64,
                "hash_scope": "FULL_FILE",
                "method": "INDEPENDENT_SHA256_READ",
            },
            "selected_frame_count": 1,
        }
        for key, value in [
            ("selected_frames_sha256", frames),
            ("preprocessing_sha256", pre),
            ("energy_labels_sha256", labels),
        ]:
            raw = canonical_bytes(value)
            sha = hashlib.sha256(raw).hexdigest()
            artifacts[sha] = raw
            source[key] = sha
        sources.append(source)
    manifest = {
        "schema_version": "rhombus-checkpoint-training-lineage-v1",
        "scope": scope,
        "checkpoint": {
            "asset_name": MODEL,
            "release_url": RELEASE_URL,
            "publisher_revision": MACE_REPO_COMMIT,
            "publisher_reported_sha256": PUBLIC_SHA256,
            "independent_observation": {
                "sha256": PUBLIC_SHA256,
                "byte_length": 79462305,
                "hash_scope": "FULL_FILE",
                "method": "INDEPENDENT_SHA256_READ",
            },
        },
        "sources": sources,
        "development_group": "development",
        "identity_scheme": "STEWARD_CANONICAL_MATERIAL_TOKEN_V1",
    }
    value = {
        "manifest": manifest,
        "artifacts": artifacts,
        "receipts": [],
        "trusted_issuers": trust(scope),
    }
    reattest_lineage(value)
    return value


def reattest_lineage(value):
    manifest = value["manifest"]
    context = evidence_sha256(manifest)
    facts = [
        (
            "checkpoint",
            "checkpoint_rehashed",
            evidence_sha256(manifest["checkpoint"]["independent_observation"]),
        )
    ]
    for source in manifest["sources"]:
        facts.extend(
            [
                (
                    "source",
                    "source_rehashed",
                    evidence_sha256(source["source_observation"]),
                ),
                ("publisher", "selection_attested", evidence_sha256(source)),
                ("auditor", "selection_audited", evidence_sha256(source)),
            ]
        )
    value["receipts"] = [
        receipt(issuer, event, sha, context, scope=manifest["scope"], sequence=i + 1)
        for i, (issuer, event, sha) in enumerate(facts)
    ]


def sqlite_records(path, rows, source, protocol):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.executemany(
            "INSERT INTO metadata VALUES (?,?)",
            [("source_sha256", source), ("protocol_sha256", protocol)],
        )
        db.execute(
            "CREATE TABLE records (ordinal INTEGER, record_id TEXT, payload_sha256 TEXT)"
        )
        db.executemany("INSERT INTO records VALUES (?,?,?)", rows)
    return path


def shard_fixture(root):
    protocol = evidence_sha256({"synthetic_protocol": "v1"})
    plan = plan_record_shards(
        source_sha256=evidence_sha256({"synthetic_source": "eight rows"}),
        protocol_id="sha256:" + protocol,
        total_rows=8,
        rows_per_shard=3,
    )
    args = {
        "shard_plan": plan,
        "checkpoints": [],
        "artifacts": {},
        "trusted_issuers": trust(),
        "protocol_sha256": protocol,
        "storage_epoch": "synthetic-epoch-1",
        "trusted_root": root,
        "storage_namespace": "synthetic-fixtures",
        "development_group": "development",
    }
    for spec in plan["shards"]:
        rows = [
            [n, f"synthetic-record-{n}", evidence_sha256({"synthetic_payload": n})]
            for n in range(spec["start_row"], spec["end_row_exclusive"])
        ]
        path = sqlite_records(
            root / f"synthetic-{spec['shard_index']}.sqlite",
            rows,
            plan["source_sha256"],
            protocol,
        )
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        identity = {
            "schema_version": "rhombus-persisted-source-shard-v1",
            "scope": "SYNTHETIC",
            "plan_sha256": plan["plan_sha256"],
            "source_sha256": plan["source_sha256"],
            "protocol_sha256": protocol,
            **spec,
            "shard_count": len(plan["shards"]),
            "row_count": len(rows),
            "artifact_sha256": sha,
            "artifact_bytes": path.stat().st_size,
            "records_sha256": evidence_sha256(rows),
            "storage_epoch": args["storage_epoch"],
            "storage_namespace": args["storage_namespace"],
            "completion_state": "COMPLETED",
            "persistence_state": "PERSISTED",
        }
        subject = evidence_sha256(identity)
        source_receipt = receipt(
            "source", "shard_source_audited", subject, plan["plan_sha256"]
        )
        storage_receipt = receipt(
            "receiver",
            "shard_persisted",
            subject,
            plan["plan_sha256"],
            sequence=2,
            previous=evidence_sha256(source_receipt),
        )
        args["checkpoints"].append(
            {
                "identity": identity,
                "source_receipt": source_receipt,
                "storage_receipt": storage_receipt,
            }
        )
        args["artifacts"][sha] = path
    return args
