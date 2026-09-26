import hashlib
import json
from pathlib import Path

import pytest

from rudeus.science.contracts import canonical_bytes, digest
from rudeus.science.x_adapter import adapt_files, adapt_x_result, main, write_observation
from rudeus.science.xcheck import XInputBinding, XModelIdentity, XObservation


def model():
    return XModelIdentity(
        model_name="independent-model",
        model_family="independent-family",
        checkpoint_sha256=digest("checkpoint"),
        code_revision=digest("code"),
        implementation_id="external-runner-v1",
        training_data_id="independent-training-corpus-v1",
    )


def binding():
    return XInputBinding(
        candidate_id="candidate",
        structure_sha256=digest("structure"),
        protocol_hash=digest("protocol"),
        quantity="D_self",
        units="m2/s",
        conditions={"temperature_K": 550.0, "species": "Li"},
    )


def raw_result(value=1.2e-9):
    payload = {
        "quantity": "D_self",
        "units": "m2/s",
        "value": value,
        "estimator_id": "independent-estimator-v1",
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return raw, payload


def test_x_adapter_binds_exact_raw_result_bytes():
    raw, payload = raw_result()
    obs = adapt_x_result(
        model=model(),
        binding=binding(),
        raw_result_bytes=raw,
        result=payload,
    )

    assert obs.model_hash == model().content_hash
    assert obs.input_binding_hash == binding().content_hash
    assert obs.evidence_hash == hashlib.sha256(raw).hexdigest()
    assert obs.value == pytest.approx(1.2e-9)
    assert XObservation.from_dict(obs.to_dict()) == obs


@pytest.mark.parametrize(
    "damage",
    [
        "extra_field",
        "wrong_quantity",
        "wrong_units",
        "missing_estimator",
        "boolean_value",
        "nonfinite",
    ],
)
def test_x_adapter_fails_closed_on_invalid_external_result(damage):
    raw, payload = raw_result()
    payload = dict(payload)
    if damage == "extra_field":
        payload["claimed_pass"] = True
    elif damage == "wrong_quantity":
        payload["quantity"] = "conductivity"
    elif damage == "wrong_units":
        payload["units"] = "S/m"
    elif damage == "missing_estimator":
        payload["estimator_id"] = ""
    elif damage == "boolean_value":
        payload["value"] = True
    elif damage == "nonfinite":
        payload["value"] = float("inf")

    with pytest.raises(ValueError):
        adapt_x_result(
            model=model(),
            binding=binding(),
            raw_result_bytes=raw,
            result=payload,
        )


def test_x_adapter_file_ingestion_hashes_exact_source_bytes(tmp_path):
    m = model()
    b = binding()
    raw, payload = raw_result()

    (tmp_path / "model.json").write_bytes(canonical_bytes(m))
    (tmp_path / "binding.json").write_bytes(canonical_bytes(b))
    # Deliberately noncanonical spacing: evidence identity is exact raw source bytes.
    result_raw = json.dumps(payload, indent=2).encode()
    (tmp_path / "result.json").write_bytes(result_raw)

    obs = adapt_files(
        model_path=tmp_path / "model.json",
        binding_path=tmp_path / "binding.json",
        result_path=tmp_path / "result.json",
    )
    assert obs.evidence_hash == hashlib.sha256(result_raw).hexdigest()


def test_x_adapter_publication_is_append_only_and_idempotent(tmp_path):
    raw, payload = raw_result()
    obs = adapt_x_result(
        model=model(),
        binding=binding(),
        raw_result_bytes=raw,
        result=payload,
    )
    path = tmp_path / "x-observation.json"

    write_observation(path, obs)
    first = path.read_bytes()
    write_observation(path, obs)
    assert path.read_bytes() == first

    other_raw, other_payload = raw_result(9e-9)
    other = adapt_x_result(
        model=model(),
        binding=binding(),
        raw_result_bytes=other_raw,
        result=other_payload,
    )
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_observation(path, other)
    assert path.read_bytes() == first


def test_x_adapter_cli_emits_bound_observation(tmp_path, capsys):
    m = model()
    b = binding()
    raw, payload = raw_result()
    for name, value in (("model", m), ("binding", b)):
        (tmp_path / f"{name}.json").write_bytes(canonical_bytes(value))
    (tmp_path / "result.json").write_bytes(raw)
    output = tmp_path / "observation.json"

    rc = main([
        "--model", str(tmp_path / "model.json"),
        "--binding", str(tmp_path / "binding.json"),
        "--result", str(tmp_path / "result.json"),
        "--output", str(output),
    ])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "BOUND"
    stored = XObservation.from_dict(json.loads(output.read_bytes()))
    assert report["observation_hash"] == stored.content_hash
    assert report["evidence_hash"] == hashlib.sha256(raw).hexdigest()


def test_x_adapter_cli_refuses_schema_that_contains_scientific_verdict(tmp_path, capsys):
    m = model()
    b = binding()
    (tmp_path / "model.json").write_bytes(canonical_bytes(m))
    (tmp_path / "binding.json").write_bytes(canonical_bytes(b))
    bad = {
        "quantity": "D_self",
        "units": "m2/s",
        "value": 1e-9,
        "estimator_id": "external-v1",
        "verdict": "PASS",
    }
    (tmp_path / "result.json").write_text(json.dumps(bad), encoding="utf-8")

    rc = main([
        "--model", str(tmp_path / "model.json"),
        "--binding", str(tmp_path / "binding.json"),
        "--result", str(tmp_path / "result.json"),
        "--output", str(tmp_path / "out.json"),
    ])
    assert rc == 1
    assert not (tmp_path / "out.json").exists()
    assert json.loads(capsys.readouterr().out)["status"] == "ERROR"
