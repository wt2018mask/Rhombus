import json
import subprocess
import sys
from pathlib import Path


def test_main_based_rehearsal_never_inherits_credentials_or_submits():
    root=Path(__file__).resolve().parents[1]
    output=subprocess.check_output([sys.executable,'-m','scripts.tools.rehearse_kaggle_minimal'],cwd=root)
    report=json.loads(output)
    assert report['source']=='COMMITTED_HEAD' and report['credentials']=='NOT_INHERITED'
    assert report['minimal_controller_imports']=='PASS'
    assert report['science_module_on_main']=='MISSING_REQUIRES_FROZEN_CHECKOUT'
    assert report['provider_calls']==0 and report['production_readiness']=='NO_GO'
    assert report['implicit_ref_creation']=='DENIED' and report['synthetic_mocks'] is True
    assert report['main_mcp']=='MISSING_ADDITIONAL_TOOL_SPECS_INTERFACE'
    assert report['mcp_after_committed_file_copy']=='PASS'


def test_release_candidate_materializes_only_committed_blobs(tmp_path):
    import hashlib
    from scripts.tools.build_release_candidate_0203 import build
    root=Path(__file__).resolve().parents[1]
    revision=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD']).decode().strip()
    target=tmp_path/'candidate'
    report=build(target,revision)
    assert report['production_readiness']=='NO_GO' and report['production_mutations']==0
    from scripts.tools.build_release_candidate_0203 import CONTROLLER_FILES,EXTRA
    assert set(report['candidate_files_sha256'])==set(CONTROLLER_FILES+EXTRA)
    assert not (target/'rhombus/automation/campaign_worker_v3.py').exists()
    assert len(report['candidate_files_sha256'])==16
    for name,expected in report['candidate_files_sha256'].items():
        assert hashlib.sha256((target/name).read_bytes()).hexdigest()==expected
    import pytest
    with pytest.raises(FileExistsError):build(target,revision)
