import json
import subprocess
import sys
from pathlib import Path
from tests.test_tier_a_publisher_method_audit_0205 import nb


def test_cli_writes_only_metadata_and_prevents_overwrite(tmp_path):
    inp=tmp_path/'author-notebook.ipynb';inp.write_bytes(nb())
    out=tmp_path/'audit.json'
    cmd=[sys.executable,'-m','scripts.benchmark.audit_tier_a_publisher_method_0205',
         '--notebook',str(inp),'--output',str(out)]
    p=subprocess.run(cmd,capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    info=json.loads(out.read_text())
    assert info['notebook_optimized_code_executed'] is False
    assert 'em_dft' not in out.read_text()
    assert subprocess.run(cmd,capture_output=True).returncode != 0
    assert json.loads(out.read_text())==info
