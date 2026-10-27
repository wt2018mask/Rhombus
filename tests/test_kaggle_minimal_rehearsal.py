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
