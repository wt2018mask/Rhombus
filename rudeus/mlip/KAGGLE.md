import os, shutil, subprocess, sys

# Kaggle 멀티 GPU 환경에서 첫 번째 GPU 강제 지정
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

REPO = "/kaggle/working/Rhombus"
SHARD = 0          # Notebook A = 0
OF = 2
COMMIT_SHA = "c61757c"
WORKER = f"kaggle-scaled-s{SHARD}"

# GitHub 발급 PAT 토큰 및 사용자 정보
PAT = "YOUR_PERSONAL_ACCESS_TOKEN" 
USER = "wt2018mask"
REPO_NAME = "Rhombus"

def run(cmd, cwd=REPO):
    print("+ " + cmd, flush=True)
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    print((r.stdout or "")[-1500:], flush=True)
    if r.returncode != 0:
        print((r.stderr or "")[-3000:], file=sys.stderr, flush=True)
        raise RuntimeError(f"command failed ({r.returncode}): {cmd}")
    return r

# 1. 저장소 클론 및 커밋 체크아웃
if os.path.exists(REPO):
    shutil.rmtree(REPO)
run(f"git clone https://github.com/{USER}/{REPO_NAME}.git Rhombus", cwd="/kaggle/working")
run(f"git fetch origin && git checkout {COMMIT_SHA}")

# 2. 의존성 설치 및 연산 스크립트 실행
run("pip install -q -r requirements.txt")
run("python -c \"import os, torch; os.environ['CUDA_VISIBLE_DEVICES']='0'; assert torch.cuda.is_available(), 'NO GPU - abort'\"")

print(f"\n=== Shard {SHARD} 연산 시작 ===")
run(f"python -m rudeus.mlip.run_p1 --pending data/batches/pending "
    f"--done data/batches/done --shard {SHARD} --of {OF} "
    f"--device cuda --worker {WORKER}")

# 3. Git 커밋 및 PAT 기반 푸시
run("git config user.email 'kaggle-pilot@local' && git config user.name 'kaggle-pilot'")
run("git add data/batches/done/")
run(f"git commit -m 'p1 scaled results shard {SHARD}/{OF} ({WORKER})' || true")

push_url = f"https://{USER}:{PAT}@github.com/{USER}/{REPO_NAME}.git"
run(f"git push -f {push_url} HEAD:refs/heads/p1-scaled-s{SHARD}")

print(f"\n✅ 완료: GitHub (p1-scaled-s{SHARD})로 푸시되었습니다.")