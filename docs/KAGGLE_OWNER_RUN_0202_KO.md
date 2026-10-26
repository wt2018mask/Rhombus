# Kaggle CPU에서 0201 계산을 직접 한 번 실행하기

0202는 소유자가 실행할 Notebook과 가져오기 경로를 완성한 **엔지니어링 작업**입니다.
현재 과학 실행 상태는 `REMOTE_SCIENCE_NOT_EXECUTED`입니다. Codex 환경에는 Kaggle
인증 연결이 없으며, 소유자 계정의 무료 할당량은 이 환경에서 확인되지 않았습니다.
아래 절차는 소유자 계정에서 직접 수행하는 별도 경로입니다. 기존 sAlex 제출 금지는
그대로입니다. API 토큰·새 계정·유료 자원·로컬 MACE 실행은 필요하지 않습니다.

## 소유자가 수행할 일

1. `notebooks/Rhombus_0201_Kaggle_CPU.ipynb` 파일을 다운로드합니다.
   [Kaggle 새 Notebook](https://www.kaggle.com/code/new)을 열고 **File → Import Notebook**에서
   이 파일을 가져옵니다. 비공개 Notebook을 권장합니다.
2. Settings에서 **Accelerator = None (CPU)**, **Internet = On**을 선택합니다.
   현재 계정에서 무료 CPU 세션과 최소 3시간의 계산 예산 및 환경 설치 시간을 확보할 수 있는지
   직접 확인합니다. 계정/네트워크 기능이 제한되어 있으면 중단합니다. GPU를 선택하지 않습니다.
3. 첫 코드 셀을 실행합니다. 정확한 소스 커밋을 가져와 모든 지정 파일 해시를 확인하고,
   별도 가상환경에 고정 패키지를 설치합니다. 공식 공개 MACE 모델을 다운로드하고 전체 SHA256을
   확인합니다. **이 셀은 MD를 실행하지 않습니다.** 고정 패키지 설치나 해시 검사 실패 시
   버전을 임의 변경하지 말고 셀 오류를 보존합니다.
4. 마지막 코드 셀을 실행하고, 이전에 이 요청을 실행하지 않았는지 확인한 뒤 다음 문구를 입력합니다.

   `RUN 6bbb631e1f9329a8 FREE CPU`

   짧은 gamma-LiAlO2 CPU 탐색 계산이 먼저 실행됩니다. 실제 비용 추정이 동결 예산을 만족할 때만
   사전 선언한 두 재료의 seed/timestep 비교로 이어집니다. 수치 실패, 자원 초과 또는 예산 부족이면
   중단하며, 통과 수를 늘리기 위해 조건을 바꾸지 않습니다.
5. 셀이 끝나면 출력된 링크 또는 Kaggle Files 패널에서
   **`/kaggle/working/rhombus-thermal-6bbb631e1f9329a8.zip` 전체를 다운로드**합니다.
   COMPLETE뿐 아니라 PARTIAL/실패 결과도 보존합니다. 콘솔의 archive SHA256도 별도로 기록합니다.
   ZIP에는 요청, 원시 열 기록, NPZ 궤적, 계산 manifest, 수동 실행 기록과 로그가 포함됩니다.
   계산 전 실패이면 과학 출력이 없다는 기록과 가능한 로그를 보존합니다.
6. 실행한 Notebook의 버전 URL과 셀 출력을 별도로 보관합니다. 이미 계산했으면 **Run All로 다시
   실행하는 저장 옵션을 사용하지 않습니다.** 가능하면 재실행 없는 Quick Save로 저장합니다.
   동일 요청을 새 세션/Notebook 버전에서 다시 실행하지 않습니다. 세션 내 배타적 마커는 중복을
   막지만, 세션 간 전역 원장이나 제공자 인증을 대신하지 않습니다. 실패한 실행도 자동 재시도하지 않습니다.
7. 이 PR이 포함된 Rhombus 작업 디렉터리에서 다운로드한 ZIP을 검증합니다.

   ```bash
   python -m scripts.tools.import_manual_thermal --archive /path/to/rhombus-thermal-6bbb631e1f9329a8.zip --output-dir /path/to/new-owner-import
   ```

   콘솔에서 별도로 기록한 해시가 있으면 `--archive-sha256 <전체-SHA256>`을 추가합니다.
   모델·GPU·Kaggle CLI는 필요하지 않습니다. 가벼운 검증 의존성이 없는 환경에서는 먼저 아래를 설치합니다.

   ```bash
   python -m pip install -c scripts/ci/constraints.txt numpy scipy pymatgen ase smact pyyaml "mcp==2.3.0"
   ```

   결과의 `import-report.json`, `evidence.jsonl`과 원본 ZIP을 함께 보존합니다. 기존 MCP 서버는
   다음 스냅샷을 읽을 수 있습니다. 이 명령은 계산을 제출하지 않습니다.

   ```bash
   python -m rhombus.tools.mcp_server --evidence-jsonl /path/to/new-owner-import/evidence.jsonl
   ```

공개 모델 입력을 이미 갖고 있다면, 읽기 전용 Kaggle input으로 정확히
`mace-mpa-0-medium.model`이라는 파일 하나만 연결할 수 있습니다. 이 경우에도 해시를 확인합니다.
추가 입력이 없어도 공식 공개 다운로드를 사용하므로 Notebook 파일 하나로 시작할 수 있습니다.
어떤 경우에도 Notebook/채팅에 자격 증명을 입력하지 않습니다.

## 고정된 계산과 정체성

과학 프로토콜은 0201의 `data/development/digital0201/protocol_v1.json`과 동일합니다.
원본 요청은 변경하지 않았습니다. 새 수동 요청은
`data/development/manual0202/owner_request_v1.json`이며 원본 요청 해시를 연결합니다.
실행 소스는 **d1e6d933d429c078eb4f731670db0a7022354367**입니다. 새 수동 진입점,
Notebook 생성기, 가져오기 명령 및 실제 저장소 코드의 해시를 새 inventory에 묶었습니다.
Notebook은 그 커밋의 생성기로 결정적으로 렌더링되며 별도 release manifest에 해시가 있습니다.
생성된 셀을 임의로 편집한 결과를 동일 요청 실행으로 주장하면 안 됩니다.

재료는 보존된 COD1008166 gamma-LiAlO2와 COD9009060 Li2S의 정확한 0200 P1 구조입니다.
P0/P1을 재실행하지 않습니다. 모델은 MACE-MPA-0 medium이며 전체 SHA256은
`75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638`입니다.
CPU float64, 두 스레드, 550 K Langevin/FixCom을 사용합니다.
Python은 Linux x86_64의 3.11–3.13 범위를 검사하고 실제 버전을 기록합니다.
프로토콜의 패키지 버전이 설치되지 않으면 명확히 실패하며 대체 버전을 사용하지 않습니다.
현재 Kaggle에서 실제 설치/계산이 성공했다는 증거는 아직 없습니다.

탐색은 1 fs에서 평형화10 + 생산20 단계입니다. 사전 선언된 후속 비교는 각 재료에 대해
seed550/551의1 fs, seed550의0.5 fs 조건으로 평형화1 ps + 생산4 ps,10 fs 간격 저장입니다.
최대40,030 MD 단계,10,800초 계산, 탐색300초, 관측 RSS4096 MiB, 출력128 MiB,
1회 실행, 재시도0회, $0의 프로토콜 예산을 유지합니다. 환경 설치/모델 전송은 계산 시간과 별도입니다.
실제 탐색의 두 배 보수적 시간 추정이 전체 예산80%를 넘으면 후속 계산 없이 PARTIAL로 끝납니다.
이때도 탐색의 원시 기록을 다운로드합니다. 무료 GPU나 로컬 CPU로 자동 전환하지 않습니다.

## 결과를 어떻게 해석하는가

자동 제출용 `execute_on_kaggle`이나 `host_context`는 사용하지 않습니다. 소유자의 수동
실행 확인과 세션 내 한 번만 쓰는 마커를 사용하며, 이것을 전역 원자적 권한 소비나
인증된 제공자 관측으로 부르지 않습니다. Notebook이 쓰는 URL/식별자·완료 상태·체크섬은
독립 제공자 인증이 아닙니다. 실제 제공자 실행 ID는 확인되지 않으면 null로 유지합니다.

가져오기는 ZIP 경로 이탈·중복·심볼릭 링크·압축 해제 예산을 검사한 뒤 요청/모델/프로토콜/
소스/런타임/전체 파일 해시를 확인합니다. 실제 step/time, 온도·에너지 통계와 궤적 연결을
검증하고 기존 P2 구조 지표/판정을 원시 좌표로 다시 계산합니다. 새로운 MACE 추론은 없습니다.
검증 상태는 `ARTIFACT_MATHEMATICS_VERIFIED_ORIGIN_UNATTESTED`와
`PROVIDER_ATTESTATION_UNAVAILABLE`를 구분합니다. 수학 검증을 통과한 수동 기록만 기존
EvidenceRecord로 변환하며, INDETERMINATE/UNQUALIFIED/ABSTAIN과 제공자 인증 부재를 보존합니다.
계산 전 실패나 완료된 열 궤적이 없으면 새 과학 EvidenceRecord를 만들지 않습니다.

NVT 퍼텐셜·기계적 에너지는 보존량이 아닙니다. 온도 분포/추세와 실제 구조 지표를 따로
검토해야 하며, 기존 P2 gate와 0200 판정은 바뀌지 않습니다. NVE, 유한 크기, 장시간 수렴과
모델 적용성은 아직 미확립입니다. P2.5/P3 자격이나 전도도를 만들어내지 않습니다.
다음 과학 마일스톤은 위 Notebook의 **실제 원격 계산과 ZIP 회수·검증**입니다.
