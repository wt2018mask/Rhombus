import json
from pathlib import Path

import numpy as np
import pytest
from ase.calculators.calculator import Calculator, all_changes
from pymatgen.core import Lattice, Structure

from rudeus.science import x_mattersim_preflight as xp


class FakeMatterSimCalculator(Calculator):
    implemented_properties = ["energy", "forces", "stress"]

    def __init__(self, load_path=None, device="cuda"):
        super().__init__()
        assert load_path == xp.CHECKPOINT_LABEL
        assert device == "cuda"

    def calculate(self, atoms=None, properties=None, system_changes=all_changes):
        super().calculate(atoms, properties, system_changes)
        n = len(atoms)
        self.results = {
            "energy": float(n) * -1.25,
            "forces": np.zeros((n, 3), dtype=float),
            "stress": np.zeros(6, dtype=float),
        }


class FakeCuda:
    @staticmethod
    def is_available():
        return True

    @staticmethod
    def get_device_name(index):
        assert index == 0
        return "Fake GPU"


class FakeTorch:
    __version__ = "fake-torch"
    cuda = FakeCuda()


def batch(tmp_path):
    structure = Structure(
        Lattice.cubic(5.0),
        ["Li", "O"],
        [[0, 0, 0], [0.5, 0.5, 0.5]],
    )
    payload = {
        "batch_id": "abc123",
        "structure_sha256": "1" * 64,
        "structure_dict": structure.as_dict(),
    }
    path = tmp_path / "batch.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_mattersim_preflight_is_operational_only(tmp_path, monkeypatch):
    monkeypatch.setattr(xp, "_require_runtime", lambda: (FakeTorch(), FakeMatterSimCalculator))
    monkeypatch.setattr(xp.importlib.metadata, "version", lambda name: xp.EXPECTED_MATTERSIM_VERSION)
    checkpoint = tmp_path / "mattersim-v1.0.0-1M.pth"
    checkpoint.write_bytes(b"checkpoint")
    monkeypatch.setattr(xp, "_verified_checkpoint", lambda: (checkpoint, xp.EXPECTED_CHECKPOINT_SHA256))

    result = xp.run_preflight(batch(tmp_path))

    assert result["status"] == "PREFLIGHT_ONLY"
    assert result["scientific_x_evidence"] is False
    assert result["scientific_verdict_changed"] is False
    assert result["model_identity"]["model_family"] == "M3GNet-MatterSim"
    assert result["model_identity"]["training_data_id"] == xp.TRAINING_DATA_ID
    assert result["model_identity"]["checkpoint_sha256"] == xp.EXPECTED_CHECKPOINT_SHA256
    assert result["model_identity"]["checkpoint_size_bytes"] == len(b"checkpoint")
    assert result["single_point"]["energy_eV"] == pytest.approx(-2.5)
    assert result["single_point"]["force_max_eV_per_A"] == 0.0


def test_mattersim_preflight_rejects_disordered_structure(tmp_path, monkeypatch):
    monkeypatch.setattr(xp, "_require_runtime", lambda: (FakeTorch(), FakeMatterSimCalculator))
    structure = Structure(
        Lattice.cubic(5.0),
        [{"Li": 0.5, "Na": 0.5}],
        [[0, 0, 0]],
    )
    payload = {
        "batch_id": "abc123",
        "structure_sha256": "1" * 64,
        "structure_dict": structure.as_dict(),
    }
    path = tmp_path / "batch.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="disordered"):
        xp.run_preflight(path)


def test_mattersim_preflight_runtime_requires_python312_before_import(monkeypatch):
    class FakeVersion(tuple):
        pass

    monkeypatch.setattr(xp.sys, "version_info", FakeVersion((3, 11, 9)))
    with pytest.raises(RuntimeError, match="Python >=3.12"):
        xp._require_runtime()


def test_mattersim_preflight_cli_is_append_only(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(xp, "_require_runtime", lambda: (FakeTorch(), FakeMatterSimCalculator))
    monkeypatch.setattr(xp.importlib.metadata, "version", lambda name: xp.EXPECTED_MATTERSIM_VERSION)
    checkpoint = tmp_path / "mattersim-v1.0.0-1M.pth"
    checkpoint.write_bytes(b"checkpoint")
    monkeypatch.setattr(xp, "_verified_checkpoint", lambda: (checkpoint, xp.EXPECTED_CHECKPOINT_SHA256))
    source = batch(tmp_path)
    output = tmp_path / "preflight.json"

    assert xp.main(["--batch", str(source), "--output", str(output)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "PREFLIGHT_ONLY"
    assert report["scientific_x_evidence"] is False
    first = output.read_bytes()

    assert xp.main(["--batch", str(source), "--output", str(output)]) == 0
    capsys.readouterr()
    assert output.read_bytes() == first

    stored = json.loads(first)
    stored["status"] = "SCIENTIFIC_EVIDENCE"
    output.write_text(json.dumps(stored), encoding="utf-8")
    assert xp.main(["--batch", str(source), "--output", str(output)]) == 1
    error = json.loads(capsys.readouterr().out)
    assert error["status"] == "ERROR"


def test_mattersim_preflight_rejects_checkpoint_hash_mismatch(tmp_path, monkeypatch):
    checkpoint = tmp_path / "mattersim-v1.0.0-1M.pth"
    checkpoint.write_bytes(b"wrong-checkpoint")
    monkeypatch.setattr(xp, "_checkpoint_path", lambda: checkpoint)

    with pytest.raises(RuntimeError, match="checkpoint SHA256 mismatch"):
        xp._verified_checkpoint()


def test_mattersim_preflight_rejects_package_version_drift(tmp_path, monkeypatch):
    monkeypatch.setattr(xp, "_require_runtime", lambda: (FakeTorch(), FakeMatterSimCalculator))
    monkeypatch.setattr(xp.importlib.metadata, "version", lambda name: "9.9.9")

    with pytest.raises(RuntimeError, match="MatterSim version mismatch"):
        xp.run_preflight(batch(tmp_path))
