"""0163 independent fail-closed official TRAIN-only CSV access, no TEST field parsing."""
import hashlib
from pathlib import Path
import subprocess
import pytest
from scripts.science.obelix_train_only_transport_0163 import (
    _row_id_prefix,scan_pinned_train_only, SCHEMA,
)


def repo(tmp_path, *, test_line=b'T1,\xff,unparseable TEST experimental data,forbidden,999\n',
         extra_line=b""):
    root=tmp_path/"snapshot"
    (root/"data").mkdir(parents=True)
    (root/"data/train_idx.csv").write_bytes(b"ID\n0fh\n1dm\n")
    (root/"data/test_idx.csv").write_bytes(b"ID\nT1\n")
    source=(b"ID,Composition,Ionic conductivity (S cm-1),DOI,CIF\n"
            b"0fh,Li1.2Al0.2Ge1.8P3O12,0.00001,10.1021/acsami.8b00842,Match\n"
            +test_line+
            b"1dm,Li1.6Al0.6Ge1.4P3O12,0.0001,10.1021/acsami.8b00842,Match\n"+
            extra_line)
    (root/"data/processed.csv").write_bytes(source)
    for arg in [["init","-q"],["config","user.email","rhombus-test@example.test"],
                ["config","user.name","rhombus-test"],["add","."],
                ["commit","-qm","fixture"]]:
        subprocess.run(["git",*arg],cwd=root,check=True,capture_output=True)
    return root


def test_TEST_bad_UTF8_conductivity_and_DOI_not_parsed(tmp_path):
    root=repo(tmp_path)
    x=scan_pinned_train_only(root,official=False)
    assert x["official_TRAIN_ids"]==2
    assert x["official_TEST_ids"]==1
    assert x["source_TRAIN_parsed_rows"]==2
    assert x["source_TEST_DOI_formula_conductivity_cells_parsed"]==0
    assert x["source_TEST_CIF_bytes_read"]==0
    assert x["single_processed_CSV_stream_raw_TEST_bytes_passed_over"] is True
    assert x["source_reader_not_a_cryptographic_blind"] is True
    assert set(x["_ephemeral_train_targets"])=={"0fh","1dm"}
    assert x["TRAIN_reported_numeric_point"]==2
    assert x["processed_mixed_csv_SHA256"]==hashlib.sha256((root/"data/processed.csv").read_bytes()).hexdigest()
    # This must not claim original production commit on a synthetic fixture.
    with pytest.raises(ValueError,match="pinned SHA"):
        scan_pinned_train_only(root)


def test_source_TARGET_unchanged_when_TEST_fields_mutate_or_are_invalid(tmp_path):
    a=repo(tmp_path/"a",test_line=b"T1,\xff,\xff,\xff,\xff\n")
    b=repo(tmp_path/"b",test_line=b"T1,\xfe\x00\xff,not-a-number,10.fake/censored,INVALID\n")
    first=scan_pinned_train_only(a,official=False)
    second=scan_pinned_train_only(b,official=False)
    assert first["_ephemeral_train_targets"]==second["_ephemeral_train_targets"]
    assert first["source_TEST_DOI_formula_conductivity_cells_parsed"]==0
    assert second["source_TEST_DOI_formula_conductivity_cells_parsed"]==0


def test_invalid_TRAIN_DOI_label_and_row_rejected_but_corrupt_TEST_skipped(tmp_path):
    root=repo(tmp_path,extra_line=b"MALFORMED,x,x,x,x\n")
    with pytest.raises(ValueError,match="outside official"):
        scan_pinned_train_only(root,official=False)
    wrong=repo(tmp_path/"bad",test_line=b'T1,\xff,bogus,10.fake/x,nope\n')
    (wrong/"data/processed.csv").write_bytes(
       (wrong/"data/processed.csv").read_bytes().replace(b"0.00001,",b"INVALID,"))
    subprocess.run(["git","add","."],cwd=wrong,check=True)
    subprocess.run(["git","commit","-qm","updated"],cwd=wrong,check=True)
    with pytest.raises(ValueError,match="conductivity"):
        scan_pinned_train_only(wrong,official=False)


def test_multiline_or_malformed_TEST_row_fails_closed_without_parsing_fields(tmp_path):
    wrong=repo(tmp_path, test_line=b"T1,\xff,not even a physical CSV record\nEXTRA,untrusted,more\n")
    with pytest.raises(ValueError,match="outside official|physical-line"):
        scan_pinned_train_only(wrong,official=False)


@pytest.mark.parametrize("data",[
    b'"0fh",x',b"\xff,broken",b"no_delimiter",b",empty",
    b"../oops,value",b"0123456789"*15+b",value",
])
def test_reject_non_plain_ASCII_noncanonical_source_ID(data):
    with pytest.raises(ValueError):
        _row_id_prefix(data)


def test_missing_or_extra_official_split_id_fails_closed(tmp_path):
    root=repo(tmp_path)
    (root/"data/test_idx.csv").write_bytes(b"ID\nT1\n0fh\n")
    subprocess.run(["git","add","."],cwd=root,check=True)
    subprocess.run(["git","commit","-qm","bad-test-split"],cwd=root,check=True)
    with pytest.raises(ValueError,match="overlapping"):
        scan_pinned_train_only(root,official=False)
