"""Offline regression tests for real Kaggle output recovery problems."""
import importlib.util
import io
from pathlib import Path
from unittest.mock import patch
import zipfile

import pytest

FILE = Path(__file__).resolve().parents[1] / "scripts/kaggle/retrieve_salex_outputs.py"
spec = importlib.util.spec_from_file_location("salex_recovery", FILE)
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


class Result:
    def __init__(self, code=0, stdout=""):
        self.returncode = code
        self.stdout = stdout


def test_zero_return_code_without_files_must_fail(tmp_path):
    with patch.object(source, "call_kaggle", return_value=Result(0, "")) as mock:
        with pytest.raises(ValueError, match="output unavailable"):
            source.retrieve_kernel(tmp_path / "output", source.KERNEL, attempts=2, delay=0)
    assert mock.call_count == 2


def test_receipt_and_summary_required(tmp_path):
    root = tmp_path / "output"
    root.mkdir()
    (root / "rhombus_phase3_salex_run_receipt.json").write_text("{}")
    assert not source.required_files_present(root)
    (root / "rhombus_phase3_salex_summary.json").write_text("{}")
    assert source.required_files_present(root)


def test_ref_owner_restricted():
    assert source.DATASET_RE.fullmatch("wt2018mask/rhombus-salex-recovery")
    assert not source.DATASET_RE.fullmatch("other-account/rhombus-salex-recovery")
    assert not source.DATASET_RE.fullmatch("wt2018mask/a/../../secret")


def make_zip(path, entries):
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def test_safe_private_dataset_extraction(tmp_path):
    out = tmp_path / "out"
    def fake_kaggle(args, *, timeout=600):
        target = Path(args[args.index("-p") + 1])
        make_zip(target / "science.zip", {
            "rhombus_phase3_salex_run_receipt.json": "{}",
            "rhombus_phase3_salex_summary.json": "{}",
            "rhombus_phase3_salex_membership.sqlite.zst.part0000": "binary",
            "dataset-metadata.json": "ignored",
        })
        return Result(0)
    with patch.object(source, "call_kaggle", fake_kaggle):
        source.retrieve_dataset(out, "wt2018mask/rhombus-salex-recovery")
    assert source.required_files_present(out)
    assert not (out / "dataset-metadata.json").exists()


def test_dataset_zip_traversal_is_not_written(tmp_path):
    out = tmp_path / "out"
    def fake_kaggle(args, *, timeout=600):
        target = Path(args[args.index("-p") + 1])
        make_zip(target / "science.zip", {
            "rhombus_phase3_salex_run_receipt.json": "{}",
            "rhombus_phase3_salex_summary.json": "{}",
            "../../attack.txt": "ignored",
        })
        return Result(0)
    with patch.object(source, "call_kaggle", fake_kaggle):
        source.retrieve_dataset(out, "wt2018mask/rhombus-salex-recovery")
    assert not (tmp_path / "attack.txt").exists()


def test_provider_log_does_not_expose_secrets(capsys, tmp_path):
    with patch.object(source, "call_kaggle", return_value=Result(1, "Authorization: Bearer supersecret")):
        with pytest.raises(ValueError):
            source.retrieve_kernel(tmp_path / "out", source.KERNEL, attempts=1, delay=0)
    assert "supersecret" not in capsys.readouterr().out
