"""Disposable main-based controller rehearsal; no provider or production calls."""
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import tempfile

ROOT=Path(__file__).resolve().parents[2]
MAIN='1aaaa555a9a1ce2c9123845402fec4e664626708'
SOURCE='474df8faa7484b87f19e5679336192939598e1f7'
POLICY='921f430a7e2435c763760f9ac866306c15ac7dc14572353ca76b4a2d682a1ea2'

SMOKE=r'''
import importlib,importlib.metadata,json,os,sys
from pathlib import Path
from unittest.mock import Mock
sys.path[:0]=[sys.argv[1],sys.argv[2]]
from rhombus.automation.cli import require_ledger_protection
from rhombus.automation.controller import build_request,validate_policy
from rhombus.automation.kaggle import KaggleProvider
from rhombus.automation.ledger import ControlError,GitLedger,digest
root=Path(sys.argv[1]).resolve()
for name in ('rhombus.automation.cli','rhombus.automation.controller','rhombus.automation.kaggle','rhombus.automation.ledger','rhombus.automation.verify','rhombus.automation.archive','rhombus.automation.mcp_server'):
    module=importlib.import_module(name)
    assert Path(module.__file__).resolve().is_relative_to(root), name
assert importlib.metadata.version('kaggle')=='2.2.5'
assert importlib.metadata.version('kagglesdk')=='0.1.38'
p=json.loads((root/'rhombus/automation/policy.json').read_bytes());r=build_request()
assert digest(p)==sys.argv[3];validate_policy(p,r,sys.argv[3])
assert not os.getenv('KAGGLE_API_TOKEN') and not os.getenv('GH_TOKEN')
try:KaggleProvider('wt2018mask').authenticate();raise AssertionError('credentials accepted')
except ControlError as e:assert str(e)=='AUTHENTICATION_NOT_CONFIGURED'
g=Mock();g.call.return_value=None
try:GitLedger(g,approved_root='a'*40).read();raise AssertionError('missing ref accepted')
except ControlError as e:assert str(e)=='LEDGER_NOT_PROVISIONED'
g.reset_mock()
try:GitLedger(g).compare_and_swap(None,{'state':'x'});raise AssertionError('ref created')
except ControlError as e:assert str(e)=='LEDGER_NOT_PROVISIONED'
g.call.assert_not_called()
g.call.side_effect=ControlError('GITHUB_HTTP_403')
try:require_ledger_protection(g,'ledger');raise AssertionError('403 accepted')
except ControlError as e:assert str(e)=='GITHUB_HTTP_403'
try:importlib.import_module('rhombus.atomistics.thermal_study'); raise AssertionError('science unexpectedly present on main')
except ModuleNotFoundError:pass
from rhombus.automation.mcp_server import create_server
try:
    create_server(root/'offline-mcp.jsonl',Mock())
    raise AssertionError('main MCP interface unexpectedly supports additional_tool_specs')
except TypeError as e:
    assert 'additional_tool_specs' in str(e)
print(json.dumps({'minimal_controller_imports':'PASS','pinned_provider_packages':'PASS','policy_request':'PASS',
'missing_credentials':'FAIL_CLOSED','missing_ledger':'FAIL_CLOSED','implicit_ref_creation':'DENIED',
'protection_403':'FAIL_CLOSED','science_module_on_main':'MISSING_REQUIRES_FROZEN_CHECKOUT',
'main_mcp':'MISSING_ADDITIONAL_TOOL_SPECS_INTERFACE',
'production_readiness':'NO_GO','provider_calls':0,'synthetic_mocks':True}))
'''


def main():
    with tempfile.TemporaryDirectory(prefix='rhombus-minimal-rehearsal-') as temp:
        checkout=Path(temp)/'main'
        subprocess.run(['git','clone','--quiet','--no-hardlinks','--no-checkout',str(ROOT),str(checkout)],check=True)
        subprocess.run(['git','-C',str(checkout),'checkout','--quiet','--detach',MAIN],check=True)
        files=subprocess.check_output(['git','-C',str(ROOT),'ls-tree','-r','--name-only','HEAD','rhombus/automation']).decode().splitlines()
        for file in files:
            target=checkout/file;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(subprocess.check_output(['git','-C',str(ROOT),'show','HEAD:'+file]))
        code=Path(temp)/'smoke.py';code.write_text(SMOKE)
        env={'PATH':os.defpath,'KAGGLE_CONFIG_DIR':temp,'PYTHONDONTWRITEBYTECODE':'1'}
        result=subprocess.run([sys.executable,'-S',str(code),str(checkout),sysconfig.get_paths()['purelib'],POLICY],
                              cwd=checkout,env=env,capture_output=True,text=True,check=True)
        report=json.loads(result.stdout);report.update(main_sha=MAIN,source_sha=SOURCE,
            controller_files=files, source='COMMITTED_HEAD', credentials='NOT_INHERITED')
        mcp_path='rhombus/tools/mcp_server.py'
        (checkout/mcp_path).write_bytes(subprocess.check_output(['git','-C',str(ROOT),'show','HEAD:'+mcp_path]))
        probe='import sys;sys.path[:0]=[sys.argv[1],sys.argv[2]];from rhombus.automation.mcp_server import create_server;from pathlib import Path;from unittest.mock import Mock;create_server(Path(sys.argv[1])/"offline-mcp-after.jsonl",Mock());print("PASS")'
        checked=subprocess.run([sys.executable,'-S','-c',probe,str(checkout),sysconfig.get_paths()['purelib']],cwd=checkout,env=env,capture_output=True,text=True,check=True)
        report['mcp_after_committed_file_copy']=checked.stdout.strip()
        print(json.dumps(report,sort_keys=True))

if __name__=='__main__':main()
