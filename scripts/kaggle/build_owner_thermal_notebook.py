"""Build a deterministic owner-operated notebook; never submit or calculate."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from rhombus.atomistics.manual_thermal import build_manual_request
from rhombus.atomistics.thermal_trace import canonical_bytes

BOOTSTRAP = r'''
import hashlib, json, os, platform, subprocess, sys, urllib.request
from pathlib import Path
WORK = Path('/kaggle/working')
if not WORK.is_dir() or not Path('/kaggle/input').is_dir():
    raise RuntimeError('Kaggle CPU 세션에서만 실행하세요. 로컬 실행은 지원하지 않습니다.')
if platform.machine() not in ('x86_64', 'AMD64') or not (3,11) <= sys.version_info[:2] < (3,14):
    raise RuntimeError('지원 범위: Linux x86_64 / Python 3.11–3.13. 버전을 임의 교체하지 마세요.')
if Path('/dev/nvidia0').exists() or os.environ.get('TPU_NAME'):
    raise RuntimeError('Settings → Accelerator = None (CPU)를 선택하세요.')
REPO = WORK / ('rhombus-source-' + REQUEST['task']['code_revision'][:12])
def command(args, **kw):
    subprocess.run(args, check=True, timeout=900, **kw)
if not REPO.exists():
    command(['git','init',str(REPO)])
    command(['git','-C',str(REPO),'remote','add','origin','https://github.com/wt2018mask/Rhombus.git'])
    command(['git','-C',str(REPO),'fetch','--depth=1','origin',REQUEST['task']['code_revision']])
    command(['git','-C',str(REPO),'checkout','--detach','FETCH_HEAD'])
if subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD']).decode().strip()!=REQUEST['task']['code_revision']:
    raise RuntimeError('source commit mismatch')
for name, expected in REQUEST['source_inventory'].items():
    path=REPO/name
    if path.is_symlink() or not path.resolve().is_relative_to(REPO.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        raise RuntimeError('source hash mismatch: '+name)
REQUEST_PATH=WORK/('owner-request-'+REQUEST['launch_id'][:16]+'.json')
request_bytes=(json.dumps(REQUEST,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
if REQUEST_PATH.exists() and REQUEST_PATH.read_bytes()!=request_bytes:
    raise RuntimeError('request already exists with different bytes')
REQUEST_PATH.write_bytes(request_bytes)
os.environ.update(OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2',MPLCONFIGDIR=str(WORK/'matplotlib-cache'))
VENV=WORK/'rhombus-owner-cpu-venv'
if not VENV.exists():command([sys.executable,'-m','venv',str(VENV)])
PYTHON=str(VENV/'bin'/'python')
# Isolated public package indexes only; no notebook credentials or secret input.
command([PYTHON,'-m','pip','--isolated','install','--index-url','https://download.pytorch.org/whl/cpu','torch==2.14.1+cpu'])
command([PYTHON,'-m','pip','--isolated','install','--index-url','https://pypi.org/simple','-c',str(REPO/'scripts/ci/constraints.txt'),
         'mace-torch==0.3.16','pymatgen==2026.9.24','ase==3.29.0','smact==4.0.2','pyyaml==6.0.3'])
# Optional read-only input: a file named exactly mace-mpa-0-medium.model.
inputs=list(Path('/kaggle/input').rglob('mace-mpa-0-medium.model'))
if len(inputs)>1:raise RuntimeError('ambiguous model inputs')
MODEL=inputs[0] if inputs else WORK/'mace-mpa-0-medium.model'
if not MODEL.exists():
    url='https://github.com/ACEsuit/mace-mp/releases/download/mace_mpa_0/mace-mpa-0-medium.model'
    temporary=MODEL.with_suffix('.download')
    with urllib.request.urlopen(url,timeout=180) as source, temporary.open('xb') as target:
        count=0
        while chunk:=source.read(1048576):
            count+=len(chunk)
            if count>80000000:raise RuntimeError('model download size limit')
            target.write(chunk)
    if hashlib.sha256(temporary.read_bytes()).hexdigest()!=REQUEST['protocol']['model_sha256']:
        raise RuntimeError('model hash mismatch; never deserialize')
    temporary.rename(MODEL)
if hashlib.sha256(MODEL.read_bytes()).hexdigest()!=REQUEST['protocol']['model_sha256']:
    raise RuntimeError('wrong model weights')
print('환경과 모델 준비 완료. 아직 과학 계산은 실행하지 않았습니다.')
print('task_id:',REQUEST['task_id'])
print('다음 셀에서 무료 CPU와 최소 3시간의 잔여 세션을 직접 확인하고 1회 실행하세요.')
'''.strip()

LAUNCH = r'''
# Interactive owner action. Saving with Run All would be a NEW execution: do not do it.
phrase='RUN '+REQUEST['launch_id'][:16]+' FREE CPU'
if input('무료 CPU / 잔여 세션 예산 / 이 요청 미실행 여부 확인 후 입력: '+phrase+'\n').strip()!=phrase:
    raise PermissionError('소유자의 명시적 실행이 취소됐습니다.')
OUTPUT=WORK/('rhombus-result-'+REQUEST['launch_id'][:16])
LOG=WORK/('rhombus-run-'+REQUEST['launch_id'][:16]+'.log')
ARCHIVE=WORK/('rhombus-thermal-'+REQUEST['launch_id'][:16]+'.zip')
if OUTPUT.exists() or LOG.exists() or ARCHIVE.exists():
    raise FileExistsError('기존 실행을 보존합니다. 재시도하거나 새 세션에서 같은 요청을 다시 실행하지 마세요.')
try:
    with LOG.open('xb') as log:
        completed=subprocess.run([PYTHON,'-m','scripts.kaggle.owner_thermal_run',
            '--request',str(REQUEST_PATH),'--model',str(MODEL),'--output',str(OUTPUT),
            '--owner-launch-id',REQUEST['launch_id'],'--confirm-free-cpu'],
            cwd=REPO,stdout=log,stderr=subprocess.STDOUT,timeout=11000)
    print('계산 프로세스 종료 코드:',completed.returncode)
except subprocess.TimeoutExpired:
    print('프로세스 시간 제한. 완료된 원시 파일과 로그를 보존합니다.')
finally:
    # A separate no-inference packaging process runs after the calculator exits.
    pack='from rhombus.atomistics.manual_thermal import package_manual_result; import json,sys; print(json.dumps(package_manual_result(sys.argv[1],json.load(open(sys.argv[2])),sys.argv[3],sys.argv[4])))'
    command([PYTHON,'-c',pack,str(OUTPUT),str(REQUEST_PATH),str(LOG),str(ARCHIVE)],cwd=REPO)
from IPython.display import FileLink, display
display(FileLink(str(ARCHIVE)))
print('이 ZIP 전체를 다운로드하고, 실행된 Notebook 버전 URL도 별도로 보관하세요.')
print('archive_sha256:',hashlib.sha256(ARCHIVE.read_bytes()).hexdigest())
print('제공자 독립 인증: UNAVAILABLE. 종료 성공은 과학적 타당성 판정이 아닙니다.')
'''.strip()


def build_notebook(request):
    def cell(kind, source):
        c={'cell_type':kind,'id':hashlib.sha256(source.encode()).hexdigest()[:12],
           'metadata':{},'source':source.splitlines(keepends=True)}
        if kind=='code':c.update(execution_count=None,outputs=[])
        return c
    intro='''# Rhombus 0201 — 소유자 직접 실행, Kaggle CPU\n
Settings: Accelerator **None (CPU)**, Internet **On**, 비공개 Notebook 권장.\n
첫 코드 셀은 환경/검증 모델만 준비합니다. 마지막 셀은 명시적 입력 후 요청을 한 번 실행합니다.\n
$0 무료 CPU와 잔여 세션 예산을 직접 확인하세요. 같은 요청의 다른 세션/버전 재실행은 금지합니다.\n
자동 sAlex 제출과 독립 호스트 인증을 사용하지 않습니다. 제공자 인증은 UNAVAILABLE입니다.\n
원시 결과 ZIP은 성공/실패와 관계없이 보존하세요. Save Version의 Run All로 다시 계산하지 마세요.\n'''
    source='REQUEST = __import__("json").loads('+repr(json.dumps(request,sort_keys=True,separators=(',',':')))+')\n'+BOOTSTRAP+'\n'
    return {'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python'},'accelerator':'none','rhombus':{'task_id':request['task_id'],'launch_id':request['launch_id'],'provider_attestation':'UNAVAILABLE'}},
        'cells':[cell('markdown',intro),cell('code',source),cell('code',LAUNCH+'\n')]}


def notebook_bytes(request):
    return (json.dumps(build_notebook(request),ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-commit',required=True)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[2]
    request=build_manual_request(root,a.source_commit)
    a.output_dir.mkdir(parents=True,exist_ok=False)
    (a.output_dir/'owner_request_v1.json').write_bytes(canonical_bytes(request))
    (a.output_dir/'Rhombus_0201_Kaggle_CPU.ipynb').write_bytes(notebook_bytes(request))
    print(json.dumps({'task_id':request['task_id'],'launch_id':request['launch_id'],'state':'NOT_EXECUTED'}))


if __name__=='__main__':main()
