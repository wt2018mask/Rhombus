"""Source-only publisher method audit: never imports or executes MACE/ASE."""
import json
from copy import deepcopy
from pathlib import Path
import pytest

from rhombus.benchmark.tier_a_publisher_method_audit import (
    audit_publisher_notebook_bytes, compare_to_symmetric_tier_a_draft, read_notebook_file,
)
from tests.test_tier_a_budget_contract_0204 import ready_draft

FUNCTION = '''
def optimize(images, submitdir, n_steps = 100, fmax = 0.1):
    qn_source = FIRE(images[0], logfile=f'{submitdir}/qn_source.log')
    qn_source.run()
    qn_target = FIRE(images[-1], logfile=f'{submitdir}/qn_target.log')
    qn_target.run(fmax=fmax, steps=n_steps)
    neb = NEB(images, parallel=False, k=5.0, climb=True, method='improvedtangent')
    qn = FIRE(neb)
    qn.run(steps=n_steps)
    return neb
'''
ALIASED = '''
from mace.calculators import mace_mp
for image in images_copy:
    image.calc = mace_mp(model="small", device=device, default_dtype="float64")
'''


def nb(src=FUNCTION, alias=ALIASED, extra=None):
    cells = [dict(cell_type="code", source=src),
             dict(cell_type="code", source=alias)]
    if extra is not None:
        cells += [dict(cell_type="code", source="print('ignored')", outputs=extra)]
    return json.dumps(dict(cells=cells), sort_keys=True).encode()


def test_audit_publisher_semantics_are_not_equivalent_to_equal_fmax():
    audit=audit_publisher_notebook_bytes(nb())
    assert audit["notebook_optimized_code_executed"] is False
    assert audit["matches_observed_public_git_blob"] is False
    assert len(audit["git_blob_sha1"]) == 40
    assert audit["observed_mace_small_float64_alias"] is True
    calls=audit["run_calls"]
    assert not calls["source_endpoint"]["explicit_fmax"]
    assert calls["target_endpoint"]["explicit_fmax"]
    assert calls["target_endpoint"]["explicit_steps"]
    assert not calls["neb"]["explicit_fmax"]
    assert calls["neb"]["explicit_steps"]
    r=compare_to_symmetric_tier_a_draft(audit,ready_draft())
    assert r["symmetric_draft_not_exact_notebook_reproduction"]
    assert not r["execution_authorized"]


def test_never_execute_malicious_cell_or_read_outputs(tmp_path):
    marker=tmp_path/"MUST_NOT_EXIST"
    malicious=f"__import__('pathlib').Path({str(marker)!r}).touch()"
    audit=audit_publisher_notebook_bytes(nb(extra=[dict(output_type="display_data", data={"text/plain":["em_dft=999999"]})]))
    assert "em_dft" not in json.dumps(audit)
    custom=nb(alias=ALIASED+"\n"+malicious)
    audit_publisher_notebook_bytes(custom)
    assert not marker.exists()

@pytest.mark.parametrize("source,pattern", [
    (FUNCTION.replace("qn_source.run()", "qn_source.run(fmax=fmax)"), ""),
    (FUNCTION.replace("k=5.0", "k=8.0"), "PUBLISHER_NEB_CALL_UNEXPECTED"),
    (FUNCTION.replace("improvedtangent", "eb"), "PUBLISHER_NEB_CALL_UNEXPECTED"),
    (FUNCTION.replace("climb=True", "climb=False"), "PUBLISHER_NEB_CALL_UNEXPECTED"),
    (FUNCTION.replace("n_steps = 100", "n_steps = 500"), "PUBLISHER_OPTIMIZER_DEFAULTS_UNEXPECTED"),
    (FUNCTION.replace("fmax = 0.1", "fmax = 0.05"), "PUBLISHER_OPTIMIZER_DEFAULTS_UNEXPECTED"),
])
def test_source_changes_fail_or_report_different_semantics(source,pattern):
    if pattern:
        with pytest.raises(ValueError,match=pattern):audit_publisher_notebook_bytes(nb(src=source))
    else:
        audit=audit_publisher_notebook_bytes(nb(src=source))
        with pytest.raises(ValueError,match="PUBLISHER_METHOD_OBSERVATION_NOT_VERIFIED"):
            compare_to_symmetric_tier_a_draft(audit,ready_draft())


def test_missing_small_model_alias_rejected():
    with pytest.raises(ValueError,match="SMALL_FLOAT64_ALIAS_NOT_OBSERVED"):
        audit_publisher_notebook_bytes(nb(alias="image.calc = mace_mp(model='medium', default_dtype='float64')"))


def test_duplicates_and_invalid_notebooks_rejected():
    with pytest.raises(ValueError,match="OPTIMIZE_FUNCTION_NOT_UNIQUE"):
        audit_publisher_notebook_bytes(nb(src=FUNCTION+FUNCTION))
    for raw in (b"",b"invalid",b"{}",b"A"*2_000_001):
        with pytest.raises(ValueError):audit_publisher_notebook_bytes(raw)
    with pytest.raises(ValueError,match="CODE_CELL_SOURCE_INVALID"):
        audit_publisher_notebook_bytes(json.dumps({"cells":[{"cell_type":"code","source":[1]}]}).encode())


def test_local_input_only_and_no_overwrite(tmp_path):
    file=tmp_path/"only-notebook.ipynb"; file.write_bytes(nb())
    assert read_notebook_file(file)["execution_authorized"] is False
    sym=tmp_path/"alias.ipynb"; sym.symlink_to(file)
    with pytest.raises(ValueError,match="REGULAR_LOCAL_FILE"):
        read_notebook_file(sym)
    assert file.read_bytes()==nb()


def test_method_audit_never_grants_authorization():
    audit=audit_publisher_notebook_bytes(nb())
    audit["execution_authorized"]=True
    with pytest.raises(ValueError,match="UNAUTHORIZED_METHOD_PROMOTION"):
        compare_to_symmetric_tier_a_draft(audit,ready_draft())
