import json

from rudeus.science.contracts import canonical_bytes
from rudeus.science.xnsout_cli import main
from tests.test_xnsout_production import primary, xrec, nrec


def write_json(path, value):
    path.write_bytes(canonical_bytes(value))


def test_xnsout_cli_writes_replayable_sidecars(tmp_path, capsys):
    primary_path = tmp_path / "primary.json"
    x_path = tmp_path / "x.json"
    n_path = tmp_path / "n.json"
    s_path = tmp_path / "s.json"
    out_path = tmp_path / "out.json"

    write_json(primary_path, primary().to_dict())
    write_json(x_path, xrec())
    write_json(n_path, nrec(False))

    rc = main([
        "--primary", str(primary_path),
        "--x-record", str(x_path),
        "--n-record", str(n_path),
        "--s-output", str(s_path),
        "--out-output", str(out_path),
    ])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["execution_status"] == "COMPLETED"
    assert result["final_disposition"] == "SUPPORTED"
    assert result["final_claim_verdict"] == "PASS"
    assert json.loads(s_path.read_text())["stage"] == "S"
    assert json.loads(out_path.read_text())["stage"] == "OUT"


def test_xnsout_cli_rejects_tampered_x_without_outputs(tmp_path, capsys):
    primary_path = tmp_path / "primary.json"
    x_path = tmp_path / "x.json"
    s_path = tmp_path / "s.json"
    out_path = tmp_path / "out.json"

    write_json(primary_path, primary().to_dict())
    x = xrec()
    x["assessment"]["reason_codes"] = ["forged"]
    write_json(x_path, x)

    rc = main([
        "--primary", str(primary_path),
        "--x-record", str(x_path),
        "--s-output", str(s_path),
        "--out-output", str(out_path),
    ])
    assert rc == 1
    result = json.loads(capsys.readouterr().out)
    assert result["execution_status"] == "FAILED"
    assert not s_path.exists()
    assert not out_path.exists()


def test_xnsout_cli_is_idempotent(tmp_path, capsys):
    primary_path = tmp_path / "primary.json"
    s_path = tmp_path / "s.json"
    out_path = tmp_path / "out.json"

    write_json(primary_path, primary().to_dict())

    argv = [
        "--primary", str(primary_path),
        "--s-output", str(s_path),
        "--out-output", str(out_path),
    ]
    assert main(argv) == 0
    capsys.readouterr()
    first_s = s_path.read_bytes()
    first_out = out_path.read_bytes()

    assert main(argv) == 0
    capsys.readouterr()
    assert s_path.read_bytes() == first_s
    assert out_path.read_bytes() == first_out
